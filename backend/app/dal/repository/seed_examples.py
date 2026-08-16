"""One example tool and one example workflow, seeded on first startup.

An empty Agent Studio is the hardest place to start: the tool form asks for a
FLAPI package identifier, a cube name, and a cube parameter, and none of those
are guessable from the form itself. A worked example answers "what goes in
these fields" by showing a filled one, and the workflow shows what a tool is
*for* once it exists.

The example workflow is seeded with `agent_enabled` off. The `package_id`
below is illustrative rather than a real FLAPI package, so a workflow the
agent could select would fail at run time against a live provider. Turning it
on is what the FDE does once it points at something real — the same switch
they would use to retire a route later.

Both carry `EXAMPLE_*` keys so the seeding check can tell an untouched example
from an FDE's own work, and both are deletable from the Studio like anything
else — which is the intended way to clear them once they are no longer useful.
"""

EXAMPLE_PACKAGE_KEY = "example-entity-lookup"
EXAMPLE_WORKFLOW_KEY = "example-entity-overview"

# The example tool. Field for field this is what a real FLAPI tool looks like:
# an opaque string identifier goes into a cube parameter, and the package
# returns structured rows.
EXAMPLE_PACKAGE = {
    "package_key": EXAMPLE_PACKAGE_KEY,
    "name": "דוגמה — שליפת פרטי ישות",
    "description": (
        "טול לדוגמה שמראה איך נראית הגדרת חבילת FLAPI מלאה. "
        "מקבל מזהה כמחרוזת ומחזיר את רשומת הזיהוי שלו. "
        "יש לערוך את פרטי החיבור לערכים אמיתיים לפני שימוש."
    ),
    # Deliberately not a real package: an FDE must replace it, and the name
    # says so rather than looking like a working connection.
    "package_id": "PKG-EXAMPLE-REPLACE-ME",
    "input_cube_name": "entity_cube",
    "input_cube_parameter": "entity_id",
    "input_mode": "single",
    "output_cube_name": "entity_details",
    "query_name": "identity_lookup",
    # Left out of agent routing: it is an example, and an agent picking it for
    # a real follow-up would call a package that does not exist.
    "agent_enabled": False,
    "agent_instructions": (
        "This is a demonstration tool only. Do not use it for real questions "
        "until its connection points to an existing FLAPI package. If it is "
        "summarized, write the result in Hebrew."
    ),
    "output_schema": {
        "type": "object",
        "properties": {
            "entity_id": {
                "type": "string",
                "description": "המזהה כפי שהתקבל — תמיד מחרוזת.",
                "x-summary": True,
            },
            "full_name": {
                "type": "string",
                "description": "שם הישות במרשם.",
                "x-summary": True,
            },
            "status": {
                "type": "string",
                "description": "סטטוס נוכחי במרשם.",
                "x-summary": True,
            },
            "registered_on": {
                "type": "string",
                "description": "תאריך הרישום.",
                "x-summary": True,
            },
            "city": {
                "type": "string",
                "description": "יישוב.",
                "x-summary": True,
            },
            # The one field marked out of the summary, so the example also
            # demonstrates what `x-summary: false` is for: the value stays in
            # raw evidence but never reaches the summarizing model.
            "phone": {
                "type": "string",
                "description": (
                    "טלפון — מסומן x-summary: false, ולכן נשמר בראיות "
                    "אך אינו נשלח לניסוח הסיכום."
                ),
                "x-summary": False,
            },
        },
    },
    # A complete input/output pair is what makes this a workable starting
    # point: the planner reads `example_output` for sample data.
    "example_input": ["00123"],
    "example_output": [
        {
            "entity_id": "00123",
            "full_name": "דנה כהן",
            "status": "פעיל",
            "registered_on": "2021-03-14",
            "city": "חיפה",
            "phone": "052-1234567",
        },
    ],
}


def example_workflow(package_version_id: str) -> dict:
    """The example workflow, wired to the example tool that was just created.

    Takes the tool id rather than holding one, because a step must pin the
    tool row it runs and that id only exists once the tool has been written.
    """
    return {
        "workflow_key": EXAMPLE_WORKFLOW_KEY,
        "name": "דוגמה — סקירת ישות",
        "description": (
            "תהליך לדוגמה עם שלב אחד, שמראה איך טול הופך לסעיף בסיכום. "
            "פתחו אותו, ערכו את השלבים, והפעילו לסוכן כשהוא מצביע על טול אמיתי."
        ),
        "role": "detail",
        # Off until the step points at a real package: the example tool's
        # `package_id` is illustrative and would fail against a live provider.
        "agent_enabled": False,
        "system_prompt": (
            "Summarize the returned identity record: who the entity is, its "
            "status, and when it was registered. Infer nothing absent from "
            "the record. State empty fields explicitly instead of guessing. "
            "Write the result in Hebrew."
        ),
        "output_schema": {},
        "examples": [],
        "steps": [
            {
                "key": "identity",
                "name": "שליפת פרטי הישות",
                "package_version_id": package_version_id,
                "depends_on": [],
                # No incoming connection, so this lands in level 0 and the
                # canvas draws it as a step fed by the main identifier.
                "input_source": "workflow.id",
                "input_field": "",
                "summary_prompt": (
                    "Describe the identity record factually, without "
                    "judgments. Write the result in Hebrew."
                ),
            },
        ],
    }
