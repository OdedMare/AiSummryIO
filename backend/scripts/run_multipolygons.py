#!/usr/bin/env python3
"""Run a batch of drawn areas (GeoJSON MultiPolygons) against the AiSummryIO
API and collect one summary per area.

Talks to a running backend over HTTP — nothing is written straight to
Postgres. See ../../API_USAGE.md for the endpoint contract this follows.

Requires ``httpx`` (already a backend dependency — see pyproject.toml). If
you're not running inside the backend's own environment: ``pip install httpx``.

    cd backend
    python3 scripts/run_multipolygons.py \\
        --input scripts/multipolygons.example.json \\
        --output-dir ./run_results

Input is a JSON list of items:

    [
      {
        "name": "area-1",                          # optional, used for filenames/logs
        "boundaries": {"type": "MultiPolygon", "coordinates": [...]},
        "root_id": null,                            # optional, combine with boundaries if needed
        "question": "מה נמצא באזור זה?",             # optional, falls back to --question
        "skill_keys": []                             # optional, up to 3, falls back to --skill-keys
      },
      ...
    ]

Each item becomes its own conversation and its own session cookie, submitted
with `wait=0` and polled independently — see the "session cookie" and
"concurrency" sections of API_USAGE.md for why runs are never sent through
one shared cookie jar.
"""

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

_FINISHED = ("completed", "partial", "failed")
_SESSION_COOKIE = "aisummry_session"
_SUBMIT_RETRIES = 3
_SUBMIT_RETRY_BACKOFF = 2.0


class ItemError(Exception):
    """Raised for one item's failure; caught per-item so one bad area never
    aborts the batch."""


def load_items(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        items = json.load(handle)
    if not isinstance(items, list) or not items:
        raise SystemExit("%s must contain a non-empty JSON list" % path)
    for index, item in enumerate(items):
        if not item.get("boundaries") and not item.get("root_id"):
            raise SystemExit(
                "item %d (%s) has neither 'boundaries' nor 'root_id'"
                % (index, item.get("name", "?"))
            )
    return items


def _payload(item: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "root_id": item.get("root_id"),
        "boundaries": item.get("boundaries"),
        "question": item.get("question") or args.question,
        "skill_keys": item.get("skill_keys") or args.skill_keys,
    }


def submit(
    client: httpx.Client, base_url: str, item: Dict[str, Any],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """POST /summaries once, with retries for transient network errors.

    Returns {"run_id", "conversation_id", "cookie"}. The cookie is read off
    this one response and carried by hand into every later poll — see
    ``process_item`` for why each item gets its own ``httpx.Client`` rather
    than sharing one across the thread pool.
    """
    last_error: Optional[Exception] = None
    for attempt in range(1, _SUBMIT_RETRIES + 1):
        try:
            response = client.post(
                base_url + "/summaries",
                params={"wait": 0},
                json=_payload(item, args),
            )
            response.raise_for_status()
            body = response.json()
            cookie = response.cookies.get(_SESSION_COOKIE)
            if not cookie:
                raise ItemError(
                    "no session cookie in the response — cannot poll this "
                    "run safely, see API_USAGE.md"
                )
            return {
                "run_id": body["run"]["id"],
                "conversation_id": body["conversation"]["id"],
                "cookie": cookie,
            }
        except httpx.HTTPStatusError as error:
            detail = _error_detail(error.response)
            # A validation error (422) or application error (400) will not
            # succeed on retry — it is about this item's payload.
            if error.response.status_code < 500:
                raise ItemError("HTTP %d: %s" % (
                    error.response.status_code, detail
                ))
            last_error = error
        except httpx.RequestError as error:
            last_error = error
        if attempt < _SUBMIT_RETRIES:
            time.sleep(_SUBMIT_RETRY_BACKOFF * attempt)
    raise ItemError("submit failed after %d attempts: %s" % (
        _SUBMIT_RETRIES, last_error
    ))


def poll(
    client: httpx.Client, base_url: str, run_id: str, cookie: str,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """GET /runs/{id} on an interval, pinning the run's own cookie on every
    call rather than relying on the client's shared jar."""
    deadline = time.monotonic() + args.poll_timeout
    cookies = {_SESSION_COOKIE: cookie}
    while True:
        response = client.get(base_url + "/runs/%s" % run_id, cookies=cookies)
        if response.status_code != 200:
            raise ItemError("HTTP %d polling run %s: %s" % (
                response.status_code, run_id, _error_detail(response)
            ))
        run = response.json()
        if run["status"] in _FINISHED:
            return run
        if time.monotonic() >= deadline:
            raise ItemError(
                "run %s still %s after %ss (--poll-timeout)"
                % (run_id, run["status"], args.poll_timeout)
            )
        time.sleep(args.poll_interval)


def _error_detail(response: httpx.Response) -> str:
    try:
        return response.json().get("detail", response.text)
    except ValueError:
        return response.text


def process_item(
    base_url: str, index: int, item: Dict[str, Any], args: argparse.Namespace,
) -> Dict[str, Any]:
    """Run one item start to finish, on its own ``httpx.Client``.

    A client auto-merges every response's ``Set-Cookie`` into one shared
    jar, so two items submitted through the *same* client at the same moment
    would race to overwrite each other's session cookie even though each
    poll pins its own cookie explicitly. One client per item — and per
    thread, since each item runs in its own pool worker — sidesteps that
    race entirely instead of trying to out-schedule it.
    """
    name = item.get("name") or "item-%03d" % index
    started = time.monotonic()
    try:
        with httpx.Client(timeout=args.timeout) as client:
            submitted = submit(client, base_url, item, args)
            run = poll(
                client, base_url, submitted["run_id"], submitted["cookie"],
                args,
            )
        outcome = {
            "name": name,
            "ok": run["status"] != "failed",
            "run_id": run["id"],
            "conversation_id": submitted["conversation_id"],
            "status": run["status"],
            "headline": (run.get("result") or {}).get("headline", ""),
            "error": run.get("error", ""),
            "elapsed_seconds": round(time.monotonic() - started, 1),
            "run": run,
        }
    except ItemError as error:
        outcome = {
            "name": name, "ok": False, "run_id": None,
            "conversation_id": None, "status": "client_error",
            "headline": "", "error": str(error),
            "elapsed_seconds": round(time.monotonic() - started, 1),
            "run": None,
        }
    return outcome


def write_result(output_dir: Path, outcome: Dict[str, Any]) -> None:
    path = output_dir / ("%s.json" % _safe_filename(outcome["name"]))
    with path.open("w", encoding="utf-8") as handle:
        json.dump(outcome, handle, ensure_ascii=False, indent=2)


def write_manifest(output_dir: Path, outcomes: List[Dict[str, Any]]) -> None:
    fields = [
        "name", "ok", "status", "run_id", "conversation_id",
        "headline", "error", "elapsed_seconds",
    ]
    with (output_dir / "manifest.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for outcome in outcomes:
            writer.writerow({key: outcome[key] for key in fields})
    with (output_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(
            [{key: outcome[key] for key in fields} for outcome in outcomes],
            handle, ensure_ascii=False, indent=2,
        )


def _safe_filename(name: str) -> str:
    return "".join(
        char if char.isalnum() or char in "-_." else "_" for char in name
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--api-base", default="http://localhost:8000/api/v1",
        help="API base URL, e.g. http://localhost:8000/api/v1 (default: %(default)s)",
    )
    parser.add_argument(
        "--input", required=True, type=Path,
        help="Path to a JSON file holding a list of areas (see "
             "scripts/multipolygons.example.json)",
    )
    parser.add_argument(
        "--output-dir", default="./run_results", type=Path,
        help="Directory for per-area result files plus manifest.csv/.json "
             "(default: %(default)s)",
    )
    parser.add_argument(
        "--concurrency", type=int, default=4,
        help="Areas submitted and polled in parallel. Keep this near the "
             "backend's max_parallel_workflows (default 4) — more than that "
             "just grows the server queue. (default: %(default)s)",
    )
    parser.add_argument(
        "--question", default="",
        help="Default question for items that omit one.",
    )
    parser.add_argument(
        "--skill-keys", default="",
        help="Comma-separated default skill_keys (max 3) for items that "
             "omit their own.",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=1.5,
        help="Seconds between GET /runs/{id} polls (default: %(default)s)",
    )
    parser.add_argument(
        "--poll-timeout", type=float, default=280,
        help="Give up on one run after this many seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout", type=float, default=30,
        help="Per-HTTP-call timeout in seconds (default: %(default)s)",
    )
    args = parser.parse_args()
    args.skill_keys = [
        key.strip() for key in args.skill_keys.split(",") if key.strip()
    ]

    items = load_items(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    base_url = args.api_base.rstrip("/")
    outcomes: List[Optional[Dict[str, Any]]] = [None] * len(items)
    try:
        with httpx.Client(timeout=args.timeout) as health_client:
            health = health_client.get(base_url + "/health")
            health.raise_for_status()
    except httpx.HTTPError as error:
        raise SystemExit(
            "cannot reach %s (%s). Is the backend running?"
            % (base_url, error)
        )

    print("submitting %d area(s), concurrency=%d -> %s" % (
        len(items), args.concurrency, args.output_dir
    ))
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(process_item, base_url, index, item, args): index
            for index, item in enumerate(items)
        }
        for future in as_completed(futures):
            index = futures[future]
            outcome = future.result()
            outcomes[index] = outcome
            write_result(args.output_dir, outcome)
            mark = "ok" if outcome["ok"] else "FAIL"
            print("[%s] %-24s %-10s %.1fs  %s" % (
                mark, outcome["name"], outcome["status"],
                outcome["elapsed_seconds"],
                outcome["headline"] or outcome["error"],
            ))

    write_manifest(args.output_dir, outcomes)
    failures = [outcome for outcome in outcomes if not outcome["ok"]]
    print("\n%d/%d succeeded, results in %s" % (
        len(items) - len(failures), len(items), args.output_dir
    ))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
