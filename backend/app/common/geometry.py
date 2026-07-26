"""GeoJSON MultiPolygon to WKT, for FLAPI package inputs.

FLAPI cube parameters take opaque strings, so a drawn area travels as WKT
in ``PackageInputCube.values`` exactly like an identifier does. Kept
dependency-free: shapely is not in the backend wheelhouse.
"""

from typing import Any, Dict, Optional


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
