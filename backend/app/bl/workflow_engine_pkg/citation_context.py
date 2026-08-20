"""Resolving what "that record" refers to in a follow-up.

A follow-up such as "הצג לי את הרשומה הזו" names its subject by reference to a
citation the previous answer rendered. There are two ways to know which one,
and they are deliberately not equally trusted:

- **Explicit.** The client sends `citation_id` because the user asked while a
  citation or evidence record was selected. There is nothing to infer: the id
  resolves against the thread and the record is returned directly, with no
  search and no model call. This is the path that makes "show me that record"
  deterministic.
- **Implicit.** The user wrote "the record about the red house" with nothing
  selected. The previous turns' citations are matched on their own text, and
  the reference resolves **only when one candidate clearly wins**. Several
  plausible matches produce a clarification question rather than a guess —
  showing the wrong record is worse than asking which one was meant, because
  a wrong record still looks like an answer.

Matching is deliberately lexical rather than a model call: the candidates are
a short, closed list of records this conversation already cited, and the
question is which of them the user's own words name. A model would add a
failure mode and a round trip to a decision the words already determine.
"""

import re
from typing import Dict, List

from app.bl.workflow_engine_pkg import citations

# A reference resolves only when the leader is clearly ahead of the runner-up.
# Below this the honest answer is a question, not a record: two records that
# match the words equally well are exactly the case the user has to settle.
_MIN_SCORE = 1
_LEAD_RATIO = 2

# Past this the clarification lists records instead of asking a question.
_MAX_OPTIONS = 4

# Hebrew and English words that carry no discriminating power. They are what
# every such question is made of ("show me the record about…"), so scoring on
# them would rank by question length rather than by subject.
_STOPWORDS = {
    "הצג", "הצגי", "הראה", "הראי", "תראה", "תראי", "לי", "את", "זה", "זו",
    "הזה", "הזו", "הרשומה", "רשומה", "הרשומות", "המקור", "מקור", "על", "של",
    "עם", "מה", "אני", "רוצה", "תן", "תני", "בבקשה", "לגבי", "יותר", "עוד",
    "show", "me", "the", "that", "this", "record", "records", "source",
    "about", "give", "a", "an", "of", "for", "please", "with", "and",
}

_TOKEN = re.compile(r"[^\W\d_]+|\d+", re.UNICODE)


def explicit_ids(run: dict) -> List[str]:
    """Citation ids the request named outright, `citation_id` first.

    The selected citation leads because it is the one the user was looking at
    when they asked; anything in `referenced_citation_ids` is additional
    context rather than the subject.
    """
    # The worker reads the persisted run row, where the request's citation
    # fields live under `citation_context`. A run written before that column
    # existed simply has none, so this degrades to an ordinary follow-up.
    stored = run.get("citation_context")
    source = stored if isinstance(stored, dict) else run
    ids = []
    primary = (source.get("citation_id") or "").strip()
    if primary:
        ids.append(primary)
    for value in source.get("referenced_citation_ids") or []:
        text = str(value).strip()
        if text and text not in ids:
            ids.append(text)
    return ids


def thread_citations(runs: List[dict]) -> List[Dict]:
    """Every citation the conversation's finished turns published, newest last.

    Deduplicated on `citation_id` keeping the newest occurrence, because ids
    restart at "c1" on every run: within one thread the most recent turn is
    what a bare marker refers to.
    """
    found: Dict[str, Dict] = {}
    for run in runs or []:
        if run.get("status") not in ("completed", "partial"):
            continue
        for item in citations.from_result(run.get("result") or {}):
            citation_id = item.get("citation_id")
            if not citation_id:
                continue
            entry = dict(item)
            entry["run_id"] = run.get("id", "")
            found[citation_id] = entry
    return list(found.values())


def resolve_explicit(
    service, conversation: dict, run: dict
) -> List[Dict]:
    """The source records for the ids the request named, in request order.

    An id that matches nothing in the thread is skipped rather than raised:
    the answer degrades to an ordinary follow-up, which is what a stale marker
    from a deleted run should do.
    """
    ids = explicit_ids(run)
    if not ids:
        return []
    available = {
        item["citation_id"]: item
        for item in thread_citations(_thread_runs(service, conversation))
    }
    return [
        _with_record(service, available[citation_id])
        for citation_id in ids if citation_id in available
    ]


def _thread_runs(service, conversation: dict) -> List[dict]:
    """The conversation's finished runs.

    Read through `getattr` like `history.recent_turns`, so a fake or older
    repository without `conversation_runs` falls back to whatever runs the
    conversation object already carries rather than failing the follow-up.
    """
    reader = getattr(service._repository, "conversation_runs", None)
    conversation_id = conversation.get("id")
    if reader is not None and conversation_id:
        try:
            return list(reader(conversation_id))
        except Exception:
            pass
    return list(conversation.get("runs") or [])


def _with_record(service, citation: Dict) -> Dict:
    """A citation plus the bounded rows of the evidence it points at.

    The rows are what let a follow-up answer "show me that record" from the
    source itself instead of running a package again.
    """
    resolved = dict(citation)
    reader = getattr(service._repository, "evidence_record", None)
    if reader is None:
        return resolved
    try:
        page = reader(citation["run_id"], citation["evidence_id"], _RECORD_ROWS)
    except Exception:
        return resolved
    resolved["records"] = (page or {}).get("records", [])
    resolved["row_count"] = (page or {}).get("row_count", 0)
    return resolved


# Enough rows to answer "show me that record" from the citation itself. The
# drawer is still where a large source is browsed, with the pagination this
# deliberately does not reproduce.
_RECORD_ROWS = 20


def match_thread(service, conversation: dict, question: str) -> Dict:
    """Resolve an implicit reference against the whole thread's citations.

    Returns `{"citation": entry}` with the record already attached, or
    `{"ambiguous": [...]}`, or `{}` when the question names no cited record.
    """
    candidates = thread_citations(_thread_runs(service, conversation))
    match = match_implicit(question, candidates)
    if match.get("citation"):
        return {"citation": _with_record(service, match["citation"])}
    return match


def match_implicit(question: str, candidates: List[Dict]) -> Dict:
    """Which cited record the question refers to, or what to ask instead.

    Returns `{"citation": entry}` on a clear winner, `{"ambiguous": [...]}`
    when several match comparably, and `{}` when the question does not refer
    to a cited record at all — the last is the ordinary case and must stay
    cheap, since every follow-up passes through here.
    """
    if not candidates:
        return {}
    words = _tokens(question)
    if not words:
        return {}
    # Sorted on the score alone: a tie must not fall through to comparing the
    # citation dicts, which is not an ordering Python defines.
    scored = sorted(
        enumerate(candidates),
        key=lambda pair: -_score(words, pair[1]),
    )
    scores = [_score(words, item) for _index, item in scored]
    best, entry = scores[0], scored[0][1]
    if best < _MIN_SCORE:
        return {}
    rivals = [
        item for (_index, item), score in zip(scored[1:], scores[1:])
        if score * _LEAD_RATIO > best
    ]
    if rivals:
        return {"ambiguous": [entry] + rivals[:_MAX_OPTIONS - 1]}
    return {"citation": entry}


def _score(words: set, citation: Dict) -> int:
    """How many of the question's distinctive words this citation carries."""
    text = " ".join(str(citation.get(key, "")) for key in (
        "label", "step_key", "excerpt", "workflow_key",
    )) + " " + " ".join(str(value) for value in citation.get("fields", []))
    return len(words.intersection(_tokens(text)))


def _tokens(text: str) -> set:
    return {
        word for word in _TOKEN.findall((text or "").lower())
        if len(word) > 1 and word not in _STOPWORDS
    }


def clarification(matches: List[Dict]) -> dict:
    """Ask which of several cited records was meant.

    Phrased as the router's own clarification shape, so a caller renders it
    exactly like every other clarifying answer rather than learning a second
    contract for the same thing.
    """
    options = [
        {
            "label": _option_label(item),
            "answer": "הצג לי את הרשומה %s" % _option_label(item),
        }
        for item in matches[:_MAX_OPTIONS]
    ]
    return {
        "headline": "לאיזו רשומה הכוונה?",
        "summary": "יש כמה רשומות שמתאימות לשאלה. לאיזו מהן הכוונה?",
        "coverage": "",
        "key_findings": [], "risks": [], "missing_data": [],
        "suggested_questions": [option["answer"] for option in options],
        "skill_results": [], "sections": [], "partial": False,
        "needs_clarification": True,
        "recommendation": "",
        "options": options,
        "claims": [],
        "citations": [citations.public(item) for item in matches],
    }


def _option_label(citation: Dict) -> str:
    label = citation.get("label") or citation.get("step_key") or "מקור"
    excerpt = (citation.get("excerpt") or "").strip()
    return "%s — %s" % (label, excerpt[:60]) if excerpt else label


def record_answer(question: str, resolved: List[Dict]) -> dict:
    """The cited source records, returned without running anything.

    "Show me that record" is a retrieval, not a question about the data: the
    user already knows which source they want and asked to see it. Running a
    search here would return something else and call it an answer.
    """
    findings = [
        "%s · %s" % (item.get("label", ""), item.get("excerpt", ""))
        for item in resolved if item.get("excerpt")
    ]
    return {
        "headline": _record_headline(resolved),
        "summary": _record_summary(resolved),
        "coverage": "; ".join(
            "%s: %d רשומות" % (item.get("label", ""), item.get("row_count", 0))
            for item in resolved
        ),
        "key_findings": findings,
        "risks": [], "missing_data": [],
        "suggested_questions": [],
        "skill_results": [], "sections": [], "partial": False,
        # Every claim here is the record itself, so each one cites exactly the
        # citation it was read from.
        "claims": [
            {
                "text": finding,
                "citation_ids": [item["citation_id"]],
            }
            for finding, item in zip(findings, resolved)
        ],
        "citations": [citations.public(item) for item in resolved],
        "cited_records": [_cited_record(item) for item in resolved],
    }


def _record_headline(resolved: List[Dict]) -> str:
    if len(resolved) == 1:
        return "הרשומה מתוך %s" % (resolved[0].get("label") or "המקור")
    return "%d רשומות מהמקורות שצוינו" % len(resolved)


def _record_summary(resolved: List[Dict]) -> str:
    return "\n".join(
        "%s (%s): %s" % (
            item.get("label", ""), item.get("step_key", ""),
            item.get("excerpt", ""),
        )
        for item in resolved
    )


def _cited_record(citation: Dict) -> dict:
    """The rows behind one citation, in the public citation's own shape."""
    record = citations.public(citation)
    record["records"] = citation.get("records", [])
    record["run_id"] = citation.get("run_id", "")
    return record
