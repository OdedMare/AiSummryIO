"""GeoJSON MultiPolygon and WKT, for FLAPI package inputs.

FLAPI cube parameters take opaque strings, so a drawn area travels as WKT
in ``PackageInputCube.values`` exactly like an identifier does. Kept
dependency-free: shapely is not a backend dependency.

The reverse direction exists for callers that hold WKT rather than a drawn
area — a batch script reading areas out of a spreadsheet, say — and need the
GeoJSON the ``/summaries`` contract accepts.
"""

from typing import Any, Dict, List, Optional


def _format(value: float) -> str:
    text = "%.7f" % float(value)
    text = text.rstrip("0").rstrip(".")
    return text or "0"


def multipolygon_to_wkt(boundaries: Optional[Dict[str, Any]]) -> str:
    """Return an OGC WKT ``MULTIPOLYGON`` or '' when there is no geometry."""
    if not boundaries:
        return ""
    if boundaries.get("type") != "MultiPolygon":
        raise ValueError("נתמך MultiPolygon בלבד")
    polygons = boundaries.get("coordinates") or []
    rendered = []
    for polygon in polygons:
        rings = [
            "(%s)" % ", ".join(
                "%s %s" % (_format(point[0]), _format(point[1]))
                for point in ring
            )
            for ring in polygon if ring
        ]
        if rings:
            rendered.append("(%s)" % ", ".join(rings))
    if not rendered:
        return ""
    return "MULTIPOLYGON (%s)" % ", ".join(rendered)


def wkt_to_multipolygon(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse OGC WKT ``MULTIPOLYGON``/``POLYGON`` into a GeoJSON MultiPolygon.

    A lone ``POLYGON`` is wrapped as a one-polygon MultiPolygon, since that is
    the only geometry the API accepts. Returns ``None`` for empty text or an
    ``EMPTY`` geometry. Any ``Z``/``M`` ordinates past the first two are
    dropped, and an ``SRID=...;`` prefix is ignored — no reprojection happens
    here, so the coordinates must already be lng/lat.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    if cleaned[:5].upper() == "SRID=":
        cleaned = cleaned.split(";", 1)[-1].strip()
    head, _, body = cleaned.partition("(")
    # "MULTIPOLYGON Z", "MULTIPOLYGON EMPTY": the type is the first word, and
    # what follows it is a dimension tag or an empty geometry.
    words = head.upper().split()
    kind = words[0] if words else ""
    if kind not in ("MULTIPOLYGON", "POLYGON"):
        raise ValueError("נתמך MULTIPOLYGON או POLYGON בלבד")
    if not body.strip():
        return None
    inner = _inside(cleaned[cleaned.index("("):])
    if kind == "POLYGON":
        return {"type": "MultiPolygon", "coordinates": [_rings(inner)]}
    return {
        "type": "MultiPolygon",
        "coordinates": [
            _rings(_inside(polygon)) for polygon in _split_top_level(inner)
        ],
    }


def _inside(text: str) -> str:
    """The content of one balanced ``(...)`` group."""
    stripped = text.strip()
    if not stripped.startswith("(") or not stripped.endswith(")"):
        raise ValueError("WKT לא תקין: סוגריים לא מאוזנים")
    return stripped[1:-1]


def _split_top_level(body: str) -> List[str]:
    """Split on commas that sit outside any parentheses."""
    parts, depth, start = [], 0, 0
    for index, char in enumerate(body):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(body[start:index])
            start = index + 1
    parts.append(body[start:])
    return [part for part in (item.strip() for item in parts) if part]


def _rings(polygon_body: str) -> List[List[List[float]]]:
    return [_points(_inside(ring)) for ring in _split_top_level(polygon_body)]


def _points(ring_body: str) -> List[List[float]]:
    points = []
    for pair in ring_body.split(","):
        ordinates = pair.split()
        if len(ordinates) < 2:
            raise ValueError("נקודה חייבת לכלול קו אורך וקו רוחב")
        points.append([float(ordinates[0]), float(ordinates[1])])
    return points
