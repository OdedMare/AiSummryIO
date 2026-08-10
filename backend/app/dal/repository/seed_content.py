"""Built-in Skills and prompts seeded on first startup."""

SEED_CONTENT = [
    {
        "content_key": "build-summary-workflow",
        "kind": "skill",
        "name": "בניית תהליך סיכום",
        "description": "מסייע ל-FDE לבנות תהליך מחבילות FLAPI.",
        "content": """# Build a summary workflow

Guide the FDE through building one workflow. Ask about one decision at a
time; never combine two questions into one sentence.

**Language:** the FDE writes in Hebrew and reads Hebrew. Ask your questions
and write every explanation, step name, and prompt in Hebrew. Keep field
names, keys, and identifiers exactly as they are — never translate
`workflow.id`, `depends_on`, a `package_version_id`, or a step key.

## Order of inquiry
1. **What does the user get at the end?** State the summary product before
   picking any package.
2. **What is the incoming identifier?** Always a string. `00123` stays
   `00123` and is never turned into 123.
3. **Which catalog packages provide that?** Only what exists. Never invent
   a package, an HTTP call, or SQL.
4. **What is the step order?** Steps that depend on nothing come first;
   steps consuming another step's output come after it.
5. **How does each step get its input?** Exactly one of `workflow.id`,
   `workflow.boundaries`, `workflow.value` plus a non-empty `input_value`, or
   `steps.<key>` plus an `input_field` naming a field that really appears in
   that step's example output.
6. **What is the workflow role?** `baseline` always runs; `detail` runs only
   on a follow-up question; `both` runs in both cases.

## The mapping rule that fails most often
A step reading another step's output must BOTH declare it in `depends_on`
AND point at a field present in the example output. A mapping to a field
that is not in the example will be rejected when the workflow is saved.
Verify the field name against the package's `example_output` — never from
memory.

## input_mode
`single` — the package takes one identifier; it is called once per
identifier. `many` — all identifiers go in a single call. Choose according
to what the package actually supports, not what is convenient.

## Before finishing
Confirm every step has a Hebrew name a user would understand, and that the
output contract ADDS fields on top of
`summary`/`facts`/`warnings`/`suggested_questions` rather than replacing
them.

Produce a proposal only. It is loaded into the FDE's form for them to
review and save; never present it as already in place.""",
    },
    {
        "content_key": "test-summary-workflow",
        "kind": "skill",
        "name": "בדיקת תהליך סיכום",
        "description": "מריץ דוגמאות ובודק מיפויים, עובדות וראיות.",
        "content": """# Test a summary workflow

Verify a workflow before it is turned on for the agent, and report what
would break.

**Language:** report every finding in Hebrew, because the FDE reads Hebrew.
Keep field names, step keys, and identifiers untranslated inside the text.

## Check in this order — stop at the first blocking failure
1. **Identifier integrity.** The identifier stays a string end to end. A
   leading zero that disappears is a blocking failure, not a warning.
2. **Mappings.** Every `input_source` is `workflow.id`,
   `workflow.boundaries`, `workflow.value` with a non-empty `input_value`, or
   a `steps.<key>` that refers to an EARLIER step. Every `steps.<key>`
   reference is also declared in `depends_on`.
3. **Field existence.** Every `input_field` names a field that appears in
   the referenced step's example output. A missing field is blocking.
4. **Examples.** Each package has both an example input and an example
   output. These are not enforced, so a missing pair is a warning worth
   raising rather than a failure — but the planner reads `example_output`,
   so a package without one is harder to wire correctly.
5. **Evidence support.** Each fact the summary is expected to state can be
   traced to a package output field. A fact with no possible source means
   the prompt is inviting the model to guess.
6. **Boundaries.** If any step uses `workflow.boundaries`, confirm the
   failure message is clear when no area was drawn.

## Severity — do not blur these
- **Blocking**: coerced identifiers, invalid mappings, missing fields.
  These must be fixed before the workflow is enabled for the agent.
- **Warning**: thin coverage, a step likely to return zero rows, a vague
  step name. These are reported but do not block.

## Output
State which checks passed, then list blocking failures first with the exact
step and field involved, and what to change. If everything passes, say so
plainly and state what the dry run actually exercised.""",
    },
    {
        "content_key": "diagnose-summary-workflow",
        "kind": "skill",
        "name": "אבחון תהליך סיכום",
        "description": "מפריד בין כשל חבילה, מיפוי, תהליך והנחיה.",
        "content": """# Diagnose a summary workflow

Find the root cause of a bad or failed run, and separate a data problem
from a wiring problem from a prompting problem.

**Language:** write the diagnosis in Hebrew. Keep step keys, field names,
and error strings verbatim so they can be searched.

## Start from the evidence, not from the summary
Read the trace and the stored evidence rows first. The Hebrew summary is
the LAST place to look — it reflects every upstream problem and will
mislead you about which one occurred.

## Classify the root cause into exactly one of these
- **FLAPI connection** — timeouts, auth, TLS, package not found. The step
  returned no rows and recorded an error. Nothing downstream is meaningful.
- **Input** — the package ran but the identifier was wrong, empty, or a
  drawn area was missing. Zero rows with no error usually lands here.
- **Mapping** — a later step read the wrong field, or read a field that is
  always empty. Look for a step whose input list is empty while the
  previous step returned rows.
- **Output contract** — rows arrived but the schema did not describe them,
  so fields were dropped or landed under `section.fields`.
- **Skill or prompt** — the data is correct and complete, but the wording
  of the summary is wrong, hedged, or invents claims. Only conclude this
  after ruling out all four above.

## The distinction that matters most
"Zero rows" and "the step failed" are different diagnoses with different
fixes. Check whether a warning was recorded for the step before deciding.
A partial run keeps its successful sections — do not report the whole
workflow as broken when one package failed.

## Output
Name the single root cause, show the evidence that points to it, and
propose the specific change to make. Say plainly when the change would
touch a workflow the agent is already selecting, so the FDE decides
before it takes effect.""",
    },
    {
        "content_key": "summary-executive",
        "kind": "skill",
        "name": "תקציר מנהלים",
        "description": "התמונה החשובה ביותר, קצר וללא מונחים טכניים.",
        "user_selectable": True,
        "content": """# Executive brief

## What you produce
One paragraph answering "what matters right now", followed by 3-5 decisive
points.

**Language:** the summary sections you receive are in Hebrew, and your
output must be in Hebrew. Do not translate names, places, or identifiers.

## Method
1. Scan every summary section and mark the facts with the largest impact.
2. Rank by impact on a decision — not by order of appearance, not by how
   many records a section returned.
3. Merge facts that say the same thing into one point. Never repeat a fact.
4. Open with the strongest finding. Never open by describing the process or
   what was searched.

## Evidence rules
- Every point rests on a fact from the summary sections. No inference
  beyond the data.
- A number, date, or name appears only if it is written in the source.
- Partial coverage or missing information is stated openly, never hidden.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = the paragraph. `items` = the points, each standing on its own.

## Worked example
Facts: "הנכס נרשם ב-2019 על שם דנה כהן"; "קיים שעבוד פעיל מ-2021";
"בקשת היתר מ-2023 סורבה".
`summary`: "הנכס בבעלות דנה כהן משנת 2019, אך שני חסמים פעילים משפיעים על
שימוש בו: שעבוד מ-2021 ובקשת היתר שסורבה ב-2023."
`items`: ["שעבוד פעיל מ-2021 מגביל עסקאות", "בקשת היתר סורבה ב-2023",
"הבעלות עצמה רשומה ואינה במחלוקת"]

## Do not
No package jargon or field names. No recommended actions — a separate
Skill owns those. Do not write "no information found" as a point when
other facts exist.""",
    },
    {
        "content_key": "summary-risks",
        "kind": "skill",
        "name": "סיכונים ודגלים אדומים",
        "description": "מזהה חריגות, סתירות וחוסרים שדורשים תשומת לב.",
        "user_selectable": True,
        "content": """# Risks and red flags

## What you produce
A severity-ranked risk list. For each: what was found, the impact, what to
check.

**Language:** input sections are Hebrew and your output must be Hebrew.
Keep names and identifiers exactly as written.

## Method — scan for these four categories in this order
1. **Contradiction** — two sections state things that cannot both be true.
2. **Anomaly** — a value outside the expected range, a future date,
   duplicate records.
3. **Active blocker** — a lien, restriction, refusal, or open proceeding.
4. **Critical gap** — a key field empty or a package that failed, where the
   absence itself changes a conclusion.

Rank by severity: what affects a decision now comes before what merely
needs verification.

## The distinction you must never blur
Missing information is not a proven risk. "לא נמצא רישום שעבוד" is neither
"there is no lien" nor "there is a lien". Frame it as a gap requiring a
check, and say what that check would settle.

## Evidence rules
- Every risk points at the fact that produced it.
- No probability estimates and no invented severity that the data does not
  support.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = the overall risk picture in one or two sentences.
`items` = one risk per line, shaped as
"what was found — possible impact — what to check".

## Worked example
Facts: "בעלות רשומה על שם דנה כהן"; "עסקת מכר נרשמה ב-2022 לטובת אבי לוי";
"לא נמצאה רשומת שעבוד".
`items`: [
"סתירה בבעלות: הרישום על שם דנה כהן אך נרשמה עסקת מכר לאבי לוי ב-2022 —
עלול לפגוע בתוקף עסקה — לבדוק איזה רישום מעודכן",
"לא נמצאה רשומת שעבוד — ייתכן שאין שעבוד וייתכן שהחבילה לא כיסתה זאת —
לאמת מול מקור השעבודים לפני הסתמכות"
]

## If there is no risk
Say so explicitly in `summary` and return an empty `items`. Never invent a
risk to fill the list.""",
    },
    {
        "content_key": "summary-actions",
        "kind": "skill",
        "name": "צעדים מומלצים",
        "description": "הופך את הממצאים לרשימת פעולות ברורה ומעשית.",
        "user_selectable": True,
        "content": """# Recommended actions

## What you produce
A ranked action list someone could execute tomorrow morning.

**Language:** input sections are Hebrew and your output must be Hebrew.
Start each action with a Hebrew verb.

## Method
1. For each finding ask: does this require action, or is it background?
   Only the former becomes an item.
2. Phrase every action with the verb first: "לאמת", "לפנות", "לעדכן",
   "לעצור".
3. Rank by what unblocks the rest: an action that enables other actions
   comes first.
4. If a finding needs information that does not exist yet, the action IS
   obtaining that information.

## What makes an action good
- **Executable**: it says who to contact or what to check — not "to
  consider" or "to examine".
- **Connected**: you can point at the fact that produced it.
- **Specific**: "לאמת מול מקור השעבודים", not "לוודא שהכל תקין".

## Evidence rules
- Each action follows from a supplied fact. Never assert new facts.
- Never recommend an action requiring information absent from the summary;
  recommend obtaining it first.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = the single most important next step, in one sentence.
`items` = one action per line, shaped as "what to do — why".

## Worked example
Facts: "סתירה בין רישום בעלות לעסקת מכר מ-2022"; "לא נמצאה רשומת שעבוד".
`summary`: "לפני כל החלטה יש להכריע איזה רישום בעלות מעודכן."
`items`: [
"לאמת מול לשכת הרישום איזה רישום בעלות תקף — סתירה בין שני מקורות חוסמת
כל עסקה",
"לבקש אישור העדר שעבודים ממקור מוסמך — הסיכום לא כיסה שעבודים ולכן אין
להסיק שאין"
]

## If nothing warrants action
Say in `summary` that the findings require no action, and use `items` to
state which information would change that answer. Never invent actions to
fill a list.""",
    },
    {
        "content_key": "summary-timeline",
        "kind": "skill",
        "name": "ציר זמן",
        "description": "מסדר אירועים ותאריכים לפי סדר כרונולוגי.",
        "user_selectable": True,
        "content": """# Timeline

## What you produce
A sequence of events, oldest to newest, showing how the identifier reached
its current state.

**Language:** input sections are Hebrew and your output must be Hebrew.
Keep dates in the format they appear in the source.

## Method
1. Collect from every section each fact carrying a date or an explicit
   ordering.
2. Sort oldest to newest. A partial date (year only) is kept as-is and
   marked as partial.
3. If two events share a date, keep both and impose no order between them.
4. Finally, if the sequence reveals a gap or a chronological contradiction,
   state it in `summary`.

## What belongs and what does not
- **Belongs**: an event with a date, or with explicit ordering ("לאחר",
  "קדם ל").
- **Does not**: an ongoing state with no date, and any fact whose position
  you would have to guess.

## Evidence rules
- Never guess a date and never derive one from context.
- Never impose a chronological order the data does not support.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = what the sequence shows, including chronological gaps.
`items` = one event per line, shaped as "date — what happened — source".

## Worked example
Facts: "הנכס נרשם ב-2019"; "שעבוד נרשם ב-2021"; "בקשת היתר סורבה 2023";
"הבעלים מתגורר בכתובת" (no date).
`summary`: "שלושה אירועים בין 2019 ל-2023, ברצף עקבי: רישום, שעבוד, סירוב
היתר. עובדת המגורים ללא תאריך ולכן אינה בציר."
`items`: ["2019 — הנכס נרשם על שם דנה כהן — בעלות",
"2021 — נרשם שעבוד פעיל — שעבודים",
"2023 — בקשת היתר סורבה — היתרים"]

## If there is no time data
Say so explicitly in `summary` and return an empty `items`. Never build a
timeline from guesses.""",
    },
    {
        "content_key": "summary-contradictions",
        "kind": "skill",
        "name": "סתירות בין מקורות",
        "description": "משווה מקורות ומצביע היכן הם אינם מסכימים.",
        "user_selectable": True,
        "content": """# Contradictions between sources

## What you produce
A list of disagreements between summary sections, and what would settle
each one.

**Language:** input sections are Hebrew and your output must be Hebrew.
Quote conflicting values exactly as they appear.

## Method
1. Find fields appearing in more than one section: name, date, status,
   address, amount.
2. For each such field, compare the values across sections.
3. Classify every difference into one of the four categories below — the
   classification is the substance of this Skill.
4. For each real contradiction, say what would settle it: which source,
   which document, which check.

## Classify differences — not every difference is a contradiction
- **Contradiction**: two values that cannot both be true. This is what
  gets reported.
- **Timing difference**: both sources correct at different times. Say it is
  timing.
- **Resolution difference**: "תל אביב" vs "תל אביב, רוטשילד 5" —
  complementary, not conflicting.
- **Wording difference**: same content, different words. Not reported at
  all.

## Evidence rules
- Point precisely at both sections and both conflicting values.
- Never decide who is right when the data cannot settle it; say what would.
- A field present in one section and absent in another is NOT a
  contradiction — that is a coverage gap.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = whether the sources are consistent, and the most significant
contradiction if any.
`items` = shaped as
"field — source A says X, source B says Y — type — what would settle it".

## Worked example
Facts: section "בעלות": "הבעלים דנה כהן, עדכון 2019"; section "עסקאות":
"נרשמה עסקת מכר לאבי לוי ב-2022"; section "כתובות": "תל אביב" vs
"תל אביב רוטשילד 5".
`summary`: "סתירה אחת ממשית בזהות הבעלים, ובנוסף הפרש רזולוציה בכתובת."
`items`: [
"בעלים — בעלות אומרת דנה כהן (2019), עסקאות אומרות אבי לוי (2022) —
סתירה — לבדוק בלשכת הרישום איזה רישום תקף כיום",
"כתובת — כתובות אומר תל אביב מול תל אביב רוטשילד 5 — הפרש רזולוציה —
אין צורך בהכרעה, הערך המפורט מכיל את הכללי"
]

## If there are no contradictions
Say in `summary` that the sources agree on their shared fields, and return
an empty `items`.""",
    },
    {
        "content_key": "summary-entities",
        "kind": "skill",
        "name": "גורמים וקשרים",
        "description": "ממפה מי ומה מופיע בסיכום ואיך הם מקושרים.",
        "user_selectable": True,
        "content": """# Entities and relationships

## What you produce
A map of the parties around the identifier: who appears, in what role, and
what connects them to it.

**Language:** input sections are Hebrew and your output must be Hebrew.
Reproduce every name exactly as written — never normalize or translate it.

## Method
1. Collect every named entity from the sections: people, companies,
   authorities, properties, identifiers.
2. For each, determine its role FROM THE DATA ONLY — owner, applicant,
   issuer, neighbor, creditor.
3. Describe its relationship to the main identifier, and relationships
   between entities where the source states them.
4. Present entities with the tightest connection to the identifier first.

## Evidence rules
- Never merge two similar names into one entity. If they might be the same,
  say so as a possibility and keep them separate.
- Never infer a role that is not stated. "מופיע ברשומת שעבוד" is not
  "creditor" unless the source says so.
- Never invent a relationship between two entities merely because they
  appeared in the same record.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = how many entities were found and which is central.
`items` = shaped as
"name — role — connection to the identifier or another entity".

## Worked example
Facts: "הנכס רשום על שם דנה כהן"; "שעבוד לטובת בנק המזרחי"; "בקשת ההיתר
הוגשה על ידי ד. כהן".
`summary`: "שלושה גורמים סביב הנכס, כאשר דנה כהן היא הגורם המרכזי."
`items`: [
"דנה כהן — בעלת הנכס — רשומה כבעלים בחלק הבעלות",
"בנק המזרחי — מוטב שעבוד — לזכותו נרשם השעבוד על הנכס",
"ד. כהן — מבקש היתר — הגיש את בקשת ההיתר; ייתכן שזו דנה כהן אך השם מקוצר
ולא ניתן לאשר זהות"
]

## If no entities are named
Say so in `summary` and return an empty `items`. Never invent names or
roles.""",
    },
    {
        "content_key": "summary-evidence-quality",
        "kind": "skill",
        "name": "איכות הראיות",
        "description": "מעריך על מה הסיכום נשען וכמה אפשר לסמוך עליו.",
        "user_selectable": True,
        "content": """# Evidence quality

## What you produce
An assessment of the foundation the summary rests on: what is well covered
and what is fragile.

**Language:** input sections are Hebrew and your output must be Hebrew.
Keep section names exactly as supplied.

## Method
1. Go through the sections and mark each: succeeded, partial, or failed.
2. For each major conclusion, check how many sections support it.
3. Flag conclusions resting on a single section — those are the most
   fragile.
4. Flag sections that failed or returned zero rows, and say what they would
   have contributed.

## What weakens evidence — look for exactly these
- **Single source**: no cross-verification.
- **Partial coverage**: the package succeeded but returned less than
  expected, or with empty fields.
- **Failed package**: an entire domain is missing from the picture.
- **Staleness**: the fact is current as of an early date with no later
  update.

## Evidence rules
- Do not re-evaluate the facts themselves; evaluate their foundation.
- Never turn a methodological weakness into a claim that the fact is wrong.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = how well founded the summary is overall, and the main weakness.
`items` = shaped as
"what rests on what — type of weakness — what would strengthen it".

## Worked example
Facts: section "בעלות" succeeded; section "שעבודים" failed; section
"היתרים" partial.
`summary`: "הבעלות מבוססת היטב, אך תמונת החסמים חסרה: השעבודים לא נאספו
כלל וההיתרים חלקיים."
`items`: [
"מסקנת הבעלות נשענת על חלק הבעלות בלבד — מקור בודד — אימות מול מקור רישום
נוסף יחזק",
"תחום השעבודים חסר לגמרי — חבילה שנכשלה — הרצה חוזרת של חלק השעבודים
תשלים את תמונת החסמים",
"חלק ההיתרים החזיר נתונים חלקיים — כיסוי חלקי — יש לבדוק אם קיימות בקשות
נוספות שלא נאספו"
]

## If coverage is complete
Say so in `summary`, and use `items` to note which conclusions rest on a
single source.""",
    },
    {
        "content_key": "summary-data-profile",
        "kind": "skill",
        "name": "פרופיל הנתונים",
        "description": "מה נאסף, בכמה רשומות, ואיפה הכיסוי חזק או דליל.",
        "user_selectable": True,
        "content": """# Data profile

## What you produce
A picture of the dataset behind the summary: its size, its shape, and where
it is thick or thin.

**Language:** input sections are Hebrew and your output must be Hebrew. Keep
section names and field names exactly as supplied.

## Method
1. Read each section's `coverage` — it states what that section rests on.
2. Note which sections carry most of the volume and which contribute little.
3. Mark fields the sections describe as frequently empty.
4. Separate a section reporting zero rows from a section that failed.

## The distinction you must never blur
"No rows returned" and "the package failed" are not the same. The first is a
finding about the entity; the second is a finding about the collection. Never
present a failure as evidence of absence.

## Evidence rules
- Report only volumes the sections state. Where a section gives no count, say
  the volume was not reported — never estimate one.
- Do not add counts across sections into a total unless they describe the same
  unit. Rows from different packages are not addable.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = the dataset in one or two sentences: overall size and the main
coverage weakness.
`items` = one line per section, shaped as
"section — volume — coverage note".

## Worked example
Sections: "תיקים" covers 412 rows, department empty in 38; "אינטראקציות"
covers 27 rows; "שעבודים" returned zero rows.
`summary`: "עיקר הנתונים מגיעים מחלק התיקים (412 רשומות); שאר החלקים דלילים,
וחלק השעבודים לא החזיר רשומות כלל."
`items`: [
"תיקים — 412 רשומות — שדה המחלקה ריק ב-38 מהן",
"אינטראקציות — 27 רשומות — כיסוי דליל ביחס לתיקים",
"שעבודים — 0 רשומות — אין רישום לישות זו; אין זו כשלת חבילה"
]

## If volumes are not reported
Say so plainly in `summary` and name in `items` which sections omitted them.
Never fabricate a number to fill the profile.""",
    },
    {
        "content_key": "summary-distribution",
        "kind": "skill",
        "name": "התפלגויות ודפוסים",
        "description": "הרוב, המיעוט והריכוזים — מה הדפוס החוזר בנתונים.",
        "user_selectable": True,
        "content": """# Distribution and patterns

## What you produce
The dominant patterns in the data: what most records look like, and how the
rest divide.

**Language:** input sections are Hebrew and your output must be Hebrew. Keep
category values exactly as written; never translate a category name.

## Method
1. Read each section's `patterns` — distributions and ranges are collected
   there.
2. For each, name the dominant category and the share it holds.
3. Note concentration in time — a period holding an unusual share.
4. Note a category conspicuously rare where you would expect balance.

## Proportion rules
- Use a proportion only where the section supplies it, or supplies both the
  part and the whole. Never derive a percentage from a count whose denominator
  you do not have.
- "Most" means more than half and must be visible in the data. Do not use it
  loosely.
- Do not compare shares across sections describing different units.

## Evidence rules
- A pattern is a description, never a prediction. Do not extrapolate forward.
- Do not explain why a pattern exists. The data shows what, not why.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = the single strongest pattern, in one or two sentences.
`items` = one pattern per line, shaped as
"field or dimension — the split — what stands out".

## Worked example
Patterns: "412 תיקים, 263 פתוחים"; "רישוי 188, פיקוח 140, אחר 84"; "ריכוז
ב-2023: 147 תיקים".
`summary`: "רוב התיקים פתוחים (263 מתוך 412), ופעילות הפתיחה מתרכזת בבירור
בשנת 2023."
`items`: [
"סטטוס — 263 פתוחים מתוך 412 — הרוב אינו סגור",
"סוג תיק — רישוי 188, פיקוח 140, אחר 84 — שני סוגים מכסים כ-80%",
"שנת פתיחה — 147 מתוך 412 ב-2023 — ריכוז חריג בשנה אחת"
]

## If no distribution is reported
Say so in `summary` and return an empty `items`. Never invent a split.""",
    },
    {
        "content_key": "summary-outliers",
        "kind": "skill",
        "name": "חריגים ואנומליות",
        "description": "רשומות יוצאות דופן, ערכים בלתי אפשריים וכפילויות.",
        "user_selectable": True,
        "content": """# Outliers and anomalies

## What you produce
The records that do not fit: extreme values, impossible values, and
duplicates.

**Language:** input sections are Hebrew and your output must be Hebrew. Quote
values exactly as written.

## Method — scan for these four, in this order
1. **Impossible** — a future date, a negative duration, a closing date before
   its opening date.
2. **Extreme** — a value far outside the range the section describes.
3. **Duplicate** — the same identifier or record appearing more than once.
4. **Structurally odd** — a field empty in almost every row, or one entity
   holding a disproportionate share of records.

Sections collect these under `outliers`. Rank by certainty: an impossible
value is a fact, an extreme value is a question.

## The distinction you must never blur
Rare is not wrong. A single unusual record may be entirely legitimate. Say
what makes it stand out and what would confirm it — never assert it is an
error.

## Evidence rules
- Report an anomaly only where the sections give enough to see it. Do not
  infer one from a summary that reports no range.
- Do not estimate how many anomalies exist beyond those described.
- In `sources`, list only names of summary sections that were supplied.

## Format
`summary` = whether the data looks clean overall, and the most serious
anomaly.
`items` = one anomaly per line, shaped as
"what was found — why it stands out — what to check".

## Worked example
Outliers: "תיק C-2023-0041 נסגר ב-2022 ונפתח ב-2023"; "38 רשומות ללא מחלקה";
"ישות אחת מחזיקה 94 מתוך 412 התיקים".
`summary`: "הנתונים תקינים ברובם, אך נמצאה רשומה עם סדר תאריכים בלתי אפשרי
המחייבת בדיקה."
`items`: [
"תיק C-2023-0041 נסגר ב-2022 לפני פתיחתו ב-2023 — סדר תאריכים בלתי אפשרי —
לאמת מול מקור התיקים",
"38 רשומות ללא ערך במחלקה — כ-9% מהתיקים — לברר אם השדה אינו חובה",
"ישות אחת מחזיקה 94 מתוך 412 תיקים — ריכוז חריג — לוודא שאין כפילות רישום"
]

## If nothing stands out
Say so explicitly in `summary` and return an empty `items`. Never promote an
ordinary record to an anomaly to fill the list.""",
    },
    {
        "content_key": "final-summary",
        "kind": "prompt",
        "name": "סיכום מלא",
        "description": "הנחיית ברירת מחדל לחיבור כל חלקי הסיכום.",
        "content": """Merge the supplied summary sections into one answer
about the identifier.

**Language:** the sections are in Hebrew and every string you return must
be in Hebrew. Keep names and identifiers exactly as written.

Return JSON with `summary`, `key_findings`, `risks`, `missing_data`, and
`suggested_questions`.

- Use only the supplied facts and evidence. Never guess and never add
  information from outside the sections.
- `summary` explains the overall picture; open with what matters most, not
  with a description of the process.
- `key_findings` holds the decisive facts, deduplicated across sections.
- `risks` holds only concerns the facts support. A gap is not a risk.
- `missing_data` names what was not covered, including failed sections.
- `suggested_questions` proposes follow-ups the existing evidence cannot
  already answer.
- State partial coverage openly. A failed section never invalidates the
  sections that succeeded.""",
    },
    {
        "content_key": "follow-up-router",
        "kind": "prompt",
        "name": "ניתוב שאלת המשך",
        "description": "בוחר תהליך detail פעיל או משתמש בראיות קיימות.",
        "content": """Route a follow-up question.

Choose a single `workflow_key` ONLY if the existing evidence cannot answer
the question. If several workflows fit equally, return a `clarification`
instead of guessing. Never invent a tool or a workflow — use only the keys
supplied.

Any `clarification` text you return is shown to the user and must be
written in Hebrew.""",
    },
    {
        "content_key": "tool-aware-router",
        "kind": "prompt",
        "name": "ניתוב העמקה עם טולים",
        "description": "בוחר ראיות קיימות, workflow או טול עצמאי מאושר.",
        "content": """Choose exactly ONE action for the follow-up question:

- `use_cached` — the existing evidence already answers it.
- `workflow` — one of the workflows in the supplied list is needed.
- `tool` — one approved standalone tool is enough.
- `clarify` — information is missing to decide.

Prefer `workflow` when several steps are required, and `tool` when a single
lookup suffices. Use only the keys and identifiers supplied; never invent
one.

`history`, when present, holds earlier turns of this conversation, oldest
first. Read it to understand what the question refers to. When the answer is
already there, prefer `use_cached` over running the same workflow again, and
do not ask in `clarify` for something the user has already told you.

On `clarify`, ask ONE question the user can actually answer, and make it
answerable in one click:

- `clarification` — the question itself, in Hebrew. Ask about what the user
  wants to know, never about which workflow or tool to run: they did not
  write the catalog and cannot choose from it.
- `recommendation` — what you would look at first, and why, in one sentence.
- `options` — two to four real alternatives. `label` is a short button
  caption; `answer` is the full question sent as the user's next message, so
  write it as they would ask it. Put your recommendation first.

Return `options` empty when the honest answers are not a short list. A user
can always type their own question, so an invented menu is worse than none.

Any `clarification` text you return is shown to the user and must be
written in Hebrew.""",
    },
    {
        "content_key": "question-rewriter",
        "kind": "prompt",
        "name": "ניסוח מחדש של שאלת המשך",
        "description": "הופך שאלת המשך לשאלה שעומדת בפני עצמה לצורך ניתוב.",
        "content": """Restate the follow-up question so it stands on its own.

`history` holds earlier turns of this conversation, oldest first. Resolve
pronouns and elisions against it, so the question names its own subject
without the thread. Return the result in `question`.

Rules:

- Preserve the user's intent and scope. Narrow nothing and add nothing.
- Never answer the question, and never state facts as if they were part
  of it.
- Never invent an identifier, a date, or a name that does not appear in the
  history or in the question itself.
- Keep the user's language — a Hebrew question stays Hebrew.
- If the question already stands on its own, return it unchanged with
  `changed` set to false.

Set `changed` to true only when the wording actually differs.""",
    },
    {
        "content_key": "workflow-planner",
        "kind": "prompt",
        "name": "מתכנן תהליכים מטולים",
        "description": "מרכיב טיוטת workflow או מסביר איזה טול חסר.",
        "content": """You plan a workflow for an FDE to review.

Use only a `package_version_id` that exists in the supplied catalog. Chain
steps according to the output fields shown in the examples, keep every
identifier a string, and return a proposal only — it is the FDE who
saves it.

Each step uses `workflow.id`, `workflow.boundaries`, `workflow.value`, or an
earlier `steps.<key>`. Use `input_value` only with `workflow.value`; otherwise
return it as an empty string.

If the request cannot be fulfilled, do not invent a tool. Add to
`missing_tools` a precise description of the required input, the expected
output, and why the existing catalog cannot cover it.

**Language:** the FDE reads Hebrew. Write `name`, `description`,
`rationale`, `system_prompt`, step names, and every `missing_tools`
description in Hebrew. Keep `package_version_id`, step keys, and field
names exactly as they appear in the catalog — never translate them.""",
    },
]
