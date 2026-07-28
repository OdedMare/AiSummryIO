"""Deterministic mock rows per FLAPI package, in place of the real platform.

Keyed by `package_id`. Every generator is seeded from the identifier, so the
same identifier always yields the same evidence across runs — otherwise a
follow-up question would contradict the summary that preceded it.

Row shapes intentionally mirror what the seeded packages declare in their
`output_schema` and `example_output`, so the summary synthesis sees the
fields it was told to expect.
"""

import hashlib
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

# --- Hebrew value pools -----------------------------------------------------

CITIES = [
    "תל אביב-יפו", "ירושלים", "חיפה", "באר שבע", "ראשון לציון",
    "פתח תקווה", "נתניה", "אשדוד", "רמת גן", "רחובות",
]
STREETS = [
    "הרצל", "ויצמן", "בן גוריון", "ז'בוטינסקי", "אלנבי",
    "דיזנגוף", "רוטשילד", "הנביאים", "יפו", "הפלמ\"ח",
]
FIRST_NAMES = [
    "אבי", "דנה", "יוסי", "מיכל", "רון", "נועה", "איתי", "שירה",
    "עומר", "תמר", "גיא", "ליאת",
]
LAST_NAMES = [
    "כהן", "לוי", "מזרחי", "פרץ", "ביטון", "אברהם", "פרידמן",
    "שפירא", "דהן", "אזולאי",
]
STATUSES = ["פעיל", "לא פעיל", "בבדיקה", "מושהה"]
SEVERITIES = ["נמוכה", "בינונית", "גבוהה", "קריטית"]
CASE_TYPES = [
    "תלונה", "בקשת מידע", "חריגת בנייה", "מפגע בטיחותי",
    "הפרת רישוי", "פנייה יזומה",
]
DEPARTMENTS = [
    "אגף רישוי", "אגף פיקוח", "מוקד עירוני", "אגף הנדסה",
    "מחלקת גבייה", "שירות לקוחות",
]
CHANNELS = ["טלפון", "דוא\"ל", "אתר", "פנים אל פנים", "אפליקציה"]


def _seed(package_id: str, identifier: str) -> random.Random:
    """A per (package, identifier) RNG, stable across processes.

    `hash()` is salted per process in Python 3, so it cannot be used here:
    evidence would change between the initial run and a follow-up.
    """
    digest = hashlib.md5(
        ("%s|%s" % (package_id, identifier)).encode("utf-8")
    ).hexdigest()
    return random.Random(int(digest[:16], 16))


def _person(rng: random.Random) -> str:
    return "%s %s" % (rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES))


def _date(rng: random.Random, max_days_ago: int = 900) -> str:
    base = datetime(2026, 7, 27)
    return (base - timedelta(days=rng.randint(1, max_days_ago))).strftime(
        "%Y-%m-%d"
    )


def _address(rng: random.Random) -> str:
    return "%s %d, %s" % (
        rng.choice(STREETS), rng.randint(1, 180), rng.choice(CITIES)
    )


# --- Per-package generators -------------------------------------------------


def _identity(identifier: str, rng: random.Random) -> List[Dict[str, Any]]:
    """PKG-IDENTITY — one canonical record per identifier."""
    return [{
        "entity_id": identifier,
        "full_name": _person(rng),
        "status": rng.choice(STATUSES),
        "registered_on": _date(rng),
        "city": rng.choice(CITIES),
        "address": _address(rng),
        "phone": "05%d-%07d" % (rng.randint(0, 8), rng.randint(0, 9999999)),
        "record_source": "מרשם מרכזי",
    }]


def _cases(identifier: str, rng: random.Random) -> List[Dict[str, Any]]:
    """PKG-CASES — open and closed case history."""
    rows = []
    for index in range(rng.randint(2, 6)):
        opened = _date(rng)
        closed_flag = rng.random() < 0.6
        rows.append({
            "entity_id": identifier,
            "case_number": "C-%s-%04d" % (opened[:4], rng.randint(1, 9999)),
            "case_type": rng.choice(CASE_TYPES),
            "department": rng.choice(DEPARTMENTS),
            "severity": rng.choice(SEVERITIES),
            "opened_on": opened,
            "closed_on": _date(rng, 400) if closed_flag else None,
            "state": "סגור" if closed_flag else "פתוח",
            "handler": _person(rng),
        })
    return rows


def _interactions(identifier: str, rng: random.Random) -> List[Dict[str, Any]]:
    """PKG-INTERACTIONS — contact-centre touchpoints."""
    rows = []
    for _ in range(rng.randint(3, 8)):
        rows.append({
            "entity_id": identifier,
            "occurred_on": _date(rng, 500),
            "channel": rng.choice(CHANNELS),
            "department": rng.choice(DEPARTMENTS),
            "subject": rng.choice([
                "בירור מצב בקשה", "עדכון פרטים", "תלונה על שירות",
                "בקשה למסמכים", "תזכורת תשלום", "ערעור על החלטה",
            ]),
            "duration_minutes": rng.randint(2, 45),
            "resolved": rng.random() < 0.7,
        })
    return rows


def _payments(identifier: str, rng: random.Random) -> List[Dict[str, Any]]:
    """PKG-PAYMENTS — billing and arrears."""
    rows = []
    for _ in range(rng.randint(3, 7)):
        amount = round(rng.uniform(120, 8400), 2)
        paid = rng.random() < 0.65
        rows.append({
            "entity_id": identifier,
            "invoice_number": "INV-%06d" % rng.randint(1, 999999),
            "issued_on": _date(rng, 700),
            "due_on": _date(rng, 300),
            "amount_ils": amount,
            "paid": paid,
            "balance_ils": 0.0 if paid else amount,
            "category": rng.choice([
                "ארנונה", "אגרת רישוי", "היטל", "קנס", "מים וביוב",
            ]),
        })
    return rows


def _permits(identifier: str, rng: random.Random) -> List[Dict[str, Any]]:
    """PKG-PERMITS — licences and permits, with optional geometry."""
    rows = []
    for _ in range(rng.randint(1, 4)):
        longitude = round(rng.uniform(34.75, 35.25), 6)
        latitude = round(rng.uniform(31.75, 32.35), 6)
        rows.append({
            "entity_id": identifier,
            "permit_number": "P-%05d" % rng.randint(1, 99999),
            "permit_type": rng.choice([
                "רישיון עסק", "היתר בנייה", "היתר שילוט",
                "אישור תפוסה", "היתר חפירה",
            ]),
            "issued_on": _date(rng, 1200),
            "expires_on": "2027-%02d-%02d" % (
                rng.randint(1, 12), rng.randint(1, 28)
            ),
            "status": rng.choice(["בתוקף", "פג תוקף", "בהליך חידוש"]),
            "address": _address(rng),
            # Geometry is optional in this app; a row without it must survive.
            "location_wkt": (
                "POINT (%s %s)" % (longitude, latitude)
                if rng.random() < 0.7 else None
            ),
        })
    return rows


def _inspections(identifier: str, rng: random.Random) -> List[Dict[str, Any]]:
    """PKG-INSPECTIONS — field inspection findings."""
    rows = []
    for _ in range(rng.randint(1, 5)):
        passed = rng.random() < 0.55
        rows.append({
            "entity_id": identifier,
            "inspection_id": "INS-%05d" % rng.randint(1, 99999),
            "inspected_on": _date(rng, 600),
            "inspector": _person(rng),
            "result": "תקין" if passed else "נמצאו ליקויים",
            "findings": "" if passed else rng.choice([
                "חריגה מקווי בניין", "שילוט ללא היתר",
                "מפגע בטיחות באזור הכניסה", "אי-התאמה לתוכנית המאושרת",
            ]),
            "follow_up_required": not passed,
            "severity": "נמוכה" if passed else rng.choice(SEVERITIES[1:]),
        })
    return rows


def _relations(identifier: str, rng: random.Random) -> List[Dict[str, Any]]:
    """PKG-RELATIONS — linked entities, for the entity-map skill."""
    rows = []
    for _ in range(rng.randint(2, 5)):
        rows.append({
            "entity_id": identifier,
            "related_id": "%05d" % rng.randint(1, 99999),
            "related_name": _person(rng),
            "relation_type": rng.choice([
                "בעלים משותף", "מיופה כוח", "בן משפחה",
                "שותף עסקי", "כתובת משותפת",
            ]),
            "since": _date(rng, 1500),
            "confidence": round(rng.uniform(0.55, 0.99), 2),
        })
    return rows


def _area_scan(identifier: str, rng: random.Random) -> List[Dict[str, Any]]:
    """PKG-AREA — takes a WKT MULTIPOLYGON rather than an entity id."""
    rows = []
    for _ in range(rng.randint(3, 9)):
        rows.append({
            "area_wkt": identifier[:60],
            "entity_id": "%05d" % rng.randint(1, 99999),
            "name": _person(rng),
            "address": _address(rng),
            "open_cases": rng.randint(0, 6),
            "last_activity": _date(rng, 400),
        })
    return rows


GENERATORS = {
    "PKG-IDENTITY": _identity,
    "PKG-CASES": _cases,
    "PKG-INTERACTIONS": _interactions,
    "PKG-PAYMENTS": _payments,
    "PKG-PERMITS": _permits,
    "PKG-INSPECTIONS": _inspections,
    "PKG-RELATIONS": _relations,
    "PKG-AREA": _area_scan,
}


def _fallback(identifier: str, rng: random.Random) -> List[Dict[str, Any]]:
    """An unknown package still returns something shaped like evidence."""
    return [{
        "entity_id": identifier,
        "value": rng.randint(1, 1000),
        "label": rng.choice(CASE_TYPES),
        "recorded_on": _date(rng),
    }]


def rows_for(package_id: str, identifiers: List[str]) -> List[Dict[str, Any]]:
    """Every row produced by one package call, across its input values."""
    generate = GENERATORS.get(package_id, _fallback)
    rows = []
    for identifier in identifiers:
        rows.extend(generate(identifier, _seed(package_id, identifier)))
    return rows
