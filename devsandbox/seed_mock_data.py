#!/usr/bin/env python3
"""Seed the sandbox with mock FLAPI tools, workflows, and Skills.

Talks to the running backend over HTTP, so it exercises the same validation
and save rules the FDE Studio does — nothing is written straight to Postgres.

    python3 devsandbox/seed_mock_data.py [--base-url http://localhost:8000]

Safe to re-run: existing tools, workflows, and Skills are refreshed in place.

Every `package_id` here must have a generator in
`devsandbox/fake_flunks/flunks/mock_data.py`, otherwise that tool falls back
to generic rows.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

# --- Tools (FLAPI packages) -------------------------------------------------
# `package_id` is the key the mock generator dispatches on.

PACKAGES = [
    {
        "package_key": "identity",
        "name": "פרטי ישות",
        "description": "רשומת הזיהוי הקנונית של המזהה: שם, סטטוס, כתובת.",
        "package_id": "PKG-IDENTITY",
        "input_cube_name": "entity_cube",
        "input_cube_parameter": "entity_id",
        "input_mode": "single",
        "output_cube_name": "entity_details",
        "query_name": "identity_lookup",
        "agent_enabled": True,
        "agent_instructions": (
            "Use this tool to verify the entity's identity before any other "
            "check. Write the result in Hebrew."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "full_name": {"type": "string"},
                "status": {"type": "string"},
                "registered_on": {"type": "string"},
                "city": {"type": "string"},
                "address": {"type": "string"},
                "phone": {"type": "string", "x-summary": False},
                "record_source": {"type": "string"},
            },
        },
        "example_input": ["00123"],
        "example_output": [{
            "entity_id": "00123",
            "full_name": "דנה כהן",
            "status": "פעיל",
            "registered_on": "2021-03-14",
            "city": "חיפה",
            "address": "הרצל 42, חיפה",
            "phone": "052-1234567",
            "record_source": "מרשם מרכזי",
        }],
    },
    {
        "package_key": "cases",
        "name": "תיקים ופניות",
        "description": "היסטוריית תיקים פתוחים וסגורים לפי מזהה.",
        "package_id": "PKG-CASES",
        "input_cube_name": "cases_cube",
        "input_cube_parameter": "entity_id",
        "input_mode": "single",
        "output_cube_name": "cases_by_entity",
        "query_name": "case_history",
        "agent_enabled": True,
        "agent_instructions": (
            "Use this tool for questions about cases, complaints, and their "
            "handling. Write the result in Hebrew."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "case_number": {"type": "string"},
                "case_type": {"type": "string"},
                "department": {"type": "string"},
                "severity": {"type": "string"},
                "opened_on": {"type": "string"},
                "closed_on": {"type": ["string", "null"]},
                "state": {"type": "string"},
                "handler": {"type": "string"},
            },
        },
        "example_input": ["00123"],
        "example_output": [{
            "entity_id": "00123",
            "case_number": "C-2024-0417",
            "case_type": "חריגת בנייה",
            "department": "אגף פיקוח",
            "severity": "גבוהה",
            "opened_on": "2024-05-02",
            "closed_on": None,
            "state": "פתוח",
            "handler": "רון לוי",
        }],
    },
    {
        "package_key": "interactions",
        "name": "אינטראקציות שירות",
        "description": "פניות מול המוקד: ערוץ, נושא ותוצאה.",
        "package_id": "PKG-INTERACTIONS",
        "input_cube_name": "crm_cube",
        "input_cube_parameter": "entity_id",
        "input_mode": "single",
        "output_cube_name": "interactions_by_entity",
        "query_name": "service_interactions",
        "agent_enabled": True,
        "agent_instructions": (
            "Use this tool for questions about service-center interactions. "
            "Write the result in Hebrew."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "occurred_on": {"type": "string"},
                "channel": {"type": "string"},
                "department": {"type": "string"},
                "subject": {"type": "string"},
                "duration_minutes": {"type": "integer"},
                "resolved": {"type": "boolean"},
            },
        },
        "example_input": ["00123"],
        "example_output": [{
            "entity_id": "00123",
            "occurred_on": "2025-11-03",
            "channel": "טלפון",
            "department": "מוקד עירוני",
            "subject": "בירור מצב בקשה",
            "duration_minutes": 12,
            "resolved": True,
        }],
    },
    {
        "package_key": "payments",
        "name": "חיובים ותשלומים",
        "description": "חשבוניות, תשלומים ויתרות חוב.",
        "package_id": "PKG-PAYMENTS",
        "input_cube_name": "billing_cube",
        "input_cube_parameter": "entity_id",
        "input_mode": "single",
        "output_cube_name": "payments_by_entity",
        "query_name": "billing_history",
        "agent_enabled": True,
        "agent_instructions": (
            "Use this tool for questions about debts, payments, and "
            "collection. Write the result in Hebrew."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "invoice_number": {"type": "string"},
                "issued_on": {"type": "string"},
                "due_on": {"type": "string"},
                "amount_ils": {"type": "number"},
                "paid": {"type": "boolean"},
                "balance_ils": {"type": "number"},
                "category": {"type": "string"},
            },
        },
        "example_input": ["00123"],
        "example_output": [{
            "entity_id": "00123",
            "invoice_number": "INV-004512",
            "issued_on": "2025-01-11",
            "due_on": "2025-02-11",
            "amount_ils": 1840.5,
            "paid": False,
            "balance_ils": 1840.5,
            "category": "ארנונה",
        }],
    },
    {
        "package_key": "permits",
        "name": "רישיונות והיתרים",
        "description": "רישיונות והיתרים, כולל מיקום כאשר קיים.",
        "package_id": "PKG-PERMITS",
        "input_cube_name": "permits_cube",
        "input_cube_parameter": "entity_id",
        "input_mode": "single",
        "output_cube_name": "permits_by_entity",
        "query_name": "permit_registry",
        "agent_enabled": True,
        "agent_instructions": (
            "Use this tool for questions about licenses, permits, and "
            "validity. Write the result in Hebrew."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "permit_number": {"type": "string"},
                "permit_type": {"type": "string"},
                "issued_on": {"type": "string"},
                "expires_on": {"type": "string"},
                "status": {"type": "string"},
                "address": {"type": "string"},
                "location_wkt": {"type": ["string", "null"]},
            },
        },
        "example_input": ["00123"],
        "example_output": [{
            "entity_id": "00123",
            "permit_number": "P-04821",
            "permit_type": "רישיון עסק",
            "issued_on": "2023-06-01",
            "expires_on": "2027-06-01",
            "status": "בתוקף",
            "address": "דיזנגוף 88, תל אביב-יפו",
            "location_wkt": "POINT (34.774 32.079)",
        }],
    },
    {
        "package_key": "inspections",
        "name": "ביקורות שטח",
        "description": "ממצאי ביקורת, ליקויים וצורך במעקב.",
        "package_id": "PKG-INSPECTIONS",
        "input_cube_name": "inspections_cube",
        "input_cube_parameter": "entity_id",
        "input_mode": "single",
        "output_cube_name": "inspections_by_entity",
        "query_name": "inspection_findings",
        "agent_enabled": True,
        "agent_instructions": (
            "Use this tool for questions about inspections and defects. "
            "Write the result in Hebrew."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "inspection_id": {"type": "string"},
                "inspected_on": {"type": "string"},
                "inspector": {"type": "string"},
                "result": {"type": "string"},
                "findings": {"type": "string"},
                "follow_up_required": {"type": "boolean"},
                "severity": {"type": "string"},
            },
        },
        "example_input": ["00123"],
        "example_output": [{
            "entity_id": "00123",
            "inspection_id": "INS-02277",
            "inspected_on": "2025-04-19",
            "inspector": "מיכל פרץ",
            "result": "נמצאו ליקויים",
            "findings": "שילוט ללא היתר",
            "follow_up_required": True,
            "severity": "בינונית",
        }],
    },
    {
        "package_key": "relations",
        "name": "ישויות מקושרות",
        "description": "קשרים לישויות אחרות ורמת הוודאות שלהם.",
        "package_id": "PKG-RELATIONS",
        "input_cube_name": "graph_cube",
        "input_cube_parameter": "entity_id",
        "input_mode": "single",
        "output_cube_name": "relations_by_entity",
        "query_name": "entity_relations",
        "agent_enabled": True,
        "agent_instructions": (
            "Use this tool for questions about related parties. Write the "
            "result in Hebrew."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "related_id": {"type": "string"},
                "related_name": {"type": "string"},
                "relation_type": {"type": "string"},
                "since": {"type": "string"},
                "confidence": {"type": "number"},
            },
        },
        "example_input": ["00123"],
        "example_output": [{
            "entity_id": "00123",
            "related_id": "04417",
            "related_name": "עומר דהן",
            "relation_type": "שותף עסקי",
            "since": "2022-09-30",
            "confidence": 0.82,
        }],
    },
    {
        "package_key": "area-scan",
        "name": "סריקת אזור",
        "description": "ישויות בתוך אזור מצויר על המפה.",
        "package_id": "PKG-AREA",
        "input_cube_name": "geo_cube",
        "input_cube_parameter": "area_wkt",
        "input_mode": "many",
        "output_cube_name": "entities_in_area",
        "query_name": "area_scan",
        "agent_enabled": True,
        "agent_instructions": (
            "Use this tool only when the user selected an area on the map. "
            "Write the result in Hebrew."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "area_wkt": {"type": "string", "x-summary": False},
                "entity_id": {"type": "string"},
                "name": {"type": "string"},
                "address": {"type": "string"},
                "open_cases": {"type": "integer"},
                "last_activity": {"type": "string"},
            },
        },
        "example_input": ["MULTIPOLYGON (((34.7 32.0, 34.8 32.0, 34.8 32.1, 34.7 32.1, 34.7 32.0)))"],
        "example_output": [{
            "area_wkt": "MULTIPOLYGON (((34.7 32.0, ...)))",
            "entity_id": "07781",
            "name": "גיא אזולאי",
            "address": "רוטשילד 15, תל אביב-יפו",
            "open_cases": 2,
            "last_activity": "2026-02-08",
        }],
    },
]

# --- Workflows --------------------------------------------------------------
# `packages` names the package_key each step runs, resolved to its tool id at
# seed time.

WORKFLOWS = [
    {
        "workflow_key": "entity-profile",
        "name": "פרופיל ישות",
        "description": "זהות, רישוי וקשרים — הבסיס לכל סיכום.",
        "role": "baseline",
        "system_prompt": (
            "Summarize the entity profile: name, status, address, and license "
            "state. Base every claim only on evidence. Write the result in "
            "Hebrew."
        ),
        "steps": [
            {
                "key": "identity", "name": "פרטי ישות",
                "package": "identity",
                "summary_prompt": (
                    "Identify the entity and its status. Answer in Hebrew."
                ),
            },
            {
                "key": "permits", "name": "רישיונות והיתרים",
                "package": "permits", "depends_on": ["identity"],
                "summary_prompt": (
                    "State which licenses exist and whether they are valid. "
                    "Answer in Hebrew."
                ),
            },
            {
                "key": "relations", "name": "ישויות מקושרות",
                "package": "relations", "depends_on": ["identity"],
                "summary_prompt": (
                    "State which parties are related to the entity. Answer "
                    "in Hebrew."
                ),
            },
        ],
    },
    {
        "workflow_key": "risk-review",
        "name": "סקירת סיכונים",
        "description": "תיקים, ביקורות וחובות — תמונת הסיכון.",
        "role": "baseline",
        "system_prompt": (
            "Summarize risks from cases, inspections, and debts. Emphasize "
            "open defects and unpaid amounts. Write the result in Hebrew."
        ),
        "steps": [
            {
                "key": "cases", "name": "תיקים ופניות",
                "package": "cases",
                "summary_prompt": (
                    "State which cases are open and their severity. Answer "
                    "in Hebrew."
                ),
            },
            {
                "key": "inspections", "name": "ביקורות שטח",
                "package": "inspections",
                "summary_prompt": (
                    "State which defects were found and what needs follow-up. "
                    "Answer in Hebrew."
                ),
            },
            {
                "key": "payments", "name": "חיובים ותשלומים",
                "package": "payments",
                "summary_prompt": (
                    "State the outstanding balance and its source. Answer in "
                    "Hebrew."
                ),
            },
        ],
    },
    {
        "workflow_key": "service-history",
        "name": "היסטוריית שירות",
        "description": "פניות מול המוקד — נפתח לשאלות המשך.",
        "role": "detail",
        "system_prompt": (
            "Summarize the service-center interaction history, including "
            "channels, recurring topics, and resolution rate. Write the "
            "result in Hebrew."
        ),
        "steps": [
            {
                "key": "interactions", "name": "אינטראקציות שירות",
                "package": "interactions",
                "summary_prompt": (
                    "State which interactions occurred and what remained "
                    "unresolved. Answer in Hebrew."
                ),
            },
        ],
    },
    {
        "workflow_key": "billing-detail",
        "name": "פירוט חיובים",
        "description": "העמקה בחיובים לשאלות המשך על כסף.",
        "role": "detail",
        "system_prompt": (
            "Detail the charges, amounts, dates, payments, and outstanding "
            "items. Write the result in Hebrew."
        ),
        "steps": [
            {
                "key": "payments", "name": "חיובים ותשלומים",
                "package": "payments",
                "summary_prompt": (
                    "Detail each invoice and its payment status. Answer in "
                    "Hebrew."
                ),
            },
        ],
    },
    {
        "workflow_key": "area-survey",
        "name": "סקר אזור",
        "description": "ישויות באזור שסומן על המפה.",
        # `detail`, not `baseline`/`both`: a baseline workflow runs on every
        # request, and this one only has anything to say when an area was
        # drawn. As a baseline it added a "no area selected" section to every
        # summary, which dragged the final synthesis toward "nothing found".
        "role": "detail",
        "system_prompt": (
            "Summarize the entities found in the selected area and emphasize "
            "where open cases are concentrated. Write the result in Hebrew."
        ),
        "steps": [
            {
                "key": "area", "name": "סריקת אזור",
                "package": "area-scan",
                "input_source": "workflow.boundaries",
                "summary_prompt": (
                    "State which entities were found in the area and their "
                    "status. Answer in Hebrew."
                ),
            },
        ],
    },
]

# --- Skills -----------------------------------------------------------------

SKILLS = [
    {
        "content_key": "sandbox-exec-brief",
        "kind": "skill",
        "name": "תדריך מנהלים (סנדבוקס)",
        "description": "חמש נקודות קצרות להנהלה.",
        "user_selectable": True,
        "content": (
            "Write an executive brief in Hebrew with at most five points, "
            "one sentence each, based only on the supplied summary sections. "
            "Name the sections used. State missing information explicitly "
            "and never invent it."
        ),
    },
    {
        "content_key": "sandbox-next-actions",
        "kind": "skill",
        "name": "צעדים מומלצים (סנדבוקס)",
        "description": "פעולות מעשיות לפי סדר עדיפות.",
        "user_selectable": True,
        "content": (
            "Propose at most five practical actions in Hebrew, ordered by "
            "urgency. For each action, name the responsible party and the "
            "supporting evidence. Do not propose an action without evidence."
        ),
    },
]


# --- HTTP -------------------------------------------------------------------


def call(base_url, method, path, payload=None):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        base_url.rstrip("/") + path, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise SystemExit(
            "%s %s failed: HTTP %d\n%s" % (method, path, error.code, detail)
        )
    except urllib.error.URLError as error:
        raise SystemExit(
            "cannot reach %s (%s).\nIs the sandbox backend running?"
            % (base_url, error.reason)
        )


def seed_packages(base_url):
    """Create or refresh every tool; return package_key -> tool id."""
    created = {}
    existing = {
        row["package_key"]: row for row in call(
            base_url, "GET", "/api/packages"
        )
    }
    for package in PACKAGES:
        current = existing.get(package["package_key"])
        path = "/api/packages/%s" % current["id"] if current else "/api/packages"
        row = call(base_url, "PUT" if current else "POST", path, package)
        created[package["package_key"]] = row["id"]
        print("  tool     %-14s %s" % (
            package["package_key"], row["name"]
        ))
    return created


def seed_workflows(base_url, package_ids):
    """Create or refresh each workflow from tool ids."""
    existing = {
        row["workflow_key"]: row for row in call(
            base_url, "GET", "/api/workflows"
        )
    }
    for workflow in WORKFLOWS:
        payload = {
            key: value for key, value in workflow.items() if key != "steps"
        }
        payload["steps"] = [
            {
                "key": step["key"],
                "name": step["name"],
                "package_version_id": package_ids[step["package"]],
                "depends_on": step.get("depends_on", []),
                "input_source": step.get("input_source", "workflow.id"),
                "input_field": step.get("input_field", ""),
                "summary_prompt": step.get("summary_prompt", ""),
            }
            for step in workflow["steps"]
        ]
        current = existing.get(workflow["workflow_key"])
        path = "/api/workflows/%s" % current["id"] if current else "/api/workflows"
        row = call(base_url, "PUT" if current else "POST", path, payload)
        print("  workflow %-16s %-8s %s" % (
            workflow["workflow_key"], row["role"],
            "enabled" if row["agent_enabled"] else "disabled",
        ))


def seed_skills(base_url):
    existing = {
        row["content_key"]: row for row in call(
            base_url, "GET", "/api/agent-content"
        )
    }
    for skill in SKILLS:
        current = existing.get(skill["content_key"])
        path = "/api/agent-content/%s" % current["id"] if current else "/api/agent-content"
        row = call(base_url, "PUT" if current else "POST", path, skill)
        print("  skill    %-22s %s" % (
            skill["content_key"],
            "enabled" if row["agent_enabled"] else "disabled",
        ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    health = call(args.base_url, "GET", "/api/health")
    print("backend: %s (database %s)" % (
        health.get("status"), health.get("database")
    ))

    print("\nseeding tools")
    package_ids = seed_packages(args.base_url)
    print("\nseeding workflows")
    seed_workflows(args.base_url, package_ids)
    print("\nseeding skills")
    try:
        seed_skills(args.base_url)
    except SystemExit as error:
        # Built-in Skills are seeded by the backend itself; a clash here is
        # not worth failing the whole seed over.
        print("  skipped skills: %s" % error, file=sys.stderr)

    print("\ndone. open http://localhost:3100 and try identifier 00123")


if __name__ == "__main__":
    main()
