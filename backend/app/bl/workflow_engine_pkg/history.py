"""Conversation memory: prior turns, and the follow-up resolved against them.

Routing and synthesis both receive exactly one question and no thread. That
is fine for an opening request and wrong for everything after it: "ולמה?" or
"ומה לגבי השנה שעברה?" name their subject only by reference to what was just
said, so a router given the raw text has nothing to select on.

This module supplies the missing half. `recent_turns` reads the thread, and
`standalone_question` restates the follow-up so it carries its own subject.
What is persisted on the run and shown to the user stays the original text —
the rewrite is an internal routing aid, not a correction of the user.
"""

import json
import logging
from typing import Dict, List

from app.common.errors import AgentError
from app.bl.workflow_engine_pkg.schemas import REWRITE_SCHEMA

_logger = logging.getLogger(__name__)

# Enough thread for a pronoun or an elision to resolve, bounded because the
# same budget also carries evidence. Referents in practice sit in the last
# turn or two; older ones are reached through evidence, not through prose.
TURN_LIMIT = 4

# Prior answers are context, not the payload. A full summary per turn would
# crowd out the evidence the router actually selects on.
_ANSWER_LIMIT = 600

_FALLBACK_PROMPT = (
    "Restate a conversational follow-up so it stands on its own.\n"
    "Return JSON with the fields `question` and `changed`.\n"
    "Resolve pronouns and omissions from the prior conversation while "
    "preserving the user's intent and language.\n"
    "Do not answer the question, add unstated information, or invent "
    "identifiers.\n"
    "If the question already stands on its own, return it unchanged with "
    "`changed=false`. A Hebrew question must remain Hebrew."
)


def recent_turns(service, conversation: dict) -> List[Dict[str, str]]:
    """The conversation's finished question/answer pairs, oldest first.

    Returns an empty list when the conversation has no history or the
    repository predates it, so an opening question costs nothing here.
    """
    conversation_id = conversation.get("id")
    if not conversation_id:
        return []
    reader = getattr(service._repository, "conversation_history", None)
    if reader is None:
        return []
    return [_turn(item) for item in reader(conversation_id, TURN_LIMIT)]


def _turn(item: dict) -> Dict[str, str]:
    return {
        "question": (item.get("question") or "").strip(),
        "answer": _clip(item.get("answer") or ""),
    }


def _clip(answer: str) -> str:
    text = " ".join(answer.split())
    return text if len(text) <= _ANSWER_LIMIT else text[:_ANSWER_LIMIT] + "…"


def standalone_question(
    service, question: str, turns: List[Dict[str, str]]
) -> str:
    """`question` restated to stand alone, or unchanged when it already does.

    Every failure path returns the original question. A rewrite is an
    optimization for routing, so a model that errors, returns nothing, or
    returns something unusable must leave the caller exactly where it would
    have been without this module — never worse.
    """
    if not turns or not question.strip():
        return question
    try:
        result = service._llm.complete_json(
            _prompt(service), _payload(question, turns), REWRITE_SCHEMA
        )
    except AgentError as exc:
        _logger.info("question rewrite unavailable, routing raw: %s", exc)
        return question
    return _resolved(result, question)


def _prompt(service) -> str:
    return service._repository.enabled_content(
        "question-rewriter", _FALLBACK_PROMPT
    )


def _payload(question: str, turns: List[Dict[str, str]]) -> str:
    return json.dumps(
        {"history": turns, "question": question}, ensure_ascii=False
    )


def _resolved(result, question: str) -> str:
    """The rewritten question, guarded against a degenerate rewrite.

    A blank or near-empty result means the model dropped the question rather
    than restating it, and routing on that would be worse than routing on the
    original. `changed=false` is honored as the model declining to rewrite.
    """
    if not isinstance(result, dict) or not result.get("changed"):
        return question
    rewritten = (result.get("question") or "").strip()
    if len(rewritten) < 2:
        return question
    if rewritten != question:
        _logger.debug("follow-up rewritten for routing (%d chars)", len(rewritten))
    return rewritten
