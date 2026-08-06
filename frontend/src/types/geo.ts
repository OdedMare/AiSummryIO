/**
 * Geometry types for the map picker, ported from LocatoAI's `geo-query.ts`.
 *
 * Only the drawing subset is kept: SumOrAI scopes a summary by an area,
 * it does not run LocatoAI's layer/plan pipeline.
 *
 * `GeoJSONMultiPolygon` mirrors the backend contract (`models.SummaryCreate`).
 * Do not change one side without the other.
 */

/** How the user scopes the request geographically (UI concept only). */
export type GeographyMode = "none" | "polygon" | "rectangle";

/** Minimal GeoJSON Polygon (RFC 7946). Coordinates are [lng, lat]. */
export interface GeoJSONPolygon {
  type: "Polygon";
  /** Array of linear rings; first ring is the outer boundary (closed). */
  coordinates: [number, number][][];
}

/** GeoJSON MultiPolygon — the boundary shape the backend accepts. */
export interface GeoJSONMultiPolygon {
  type: "MultiPolygon";
  coordinates: [number, number][][][];
}

/** Bounding box: [minLng, minLat, maxLng, maxLat]. */
export type BBox = [number, number, number, number];

/** Map center/zoom, reported on every pan and zoom. */
export interface MapViewState {
  /** [lng, lat] — GeoJSON order, not Leaflet's. */
  center: [number, number];
  zoom: number;
  bbox: BBox;
}

/** Wraps a single drawn Polygon as the MultiPolygon the backend expects. */
export function toMultiPolygon(polygon: GeoJSONPolygon): GeoJSONMultiPolygon {
  return { type: "MultiPolygon", coordinates: [polygon.coordinates] };
}

/**
 * Combines every drawn part into the one MultiPolygon the backend expects.
 * Each part becomes its own member polygon, so the WKT `multipolygon_to_wkt`
 * emits keeps the parts separate rather than merging them into one ring.
 *
 * Returns null for an empty selection: the API contract sends `boundaries`
 * as null when no area was drawn, and an empty `coordinates` array would be
 * rejected by `GeoBoundaries` ("נדרש לפחות פוליגון אחד").
 */
export function toMultiPolygonParts(
  parts: GeoJSONPolygon[],
): GeoJSONMultiPolygon | null {
  if (!parts.length) return null;
  return {
    type: "MultiPolygon",
    coordinates: parts.map((part) => part.coordinates),
  };
}

export function bboxForPolygon(geometry: GeoJSONPolygon): BBox {
  return bboxForPoints(geometry.coordinates.flat());
}

/** Bounding box covering every part, for the status readout. */
export function bboxForParts(parts: GeoJSONPolygon[]): BBox | null {
  const points = parts.flatMap((part) => part.coordinates.flat());
  return points.length ? bboxForPoints(points) : null;
}

function bboxForPoints(points: [number, number][]): BBox {
  const lngs = points.map(([lng]) => lng);
  const lats = points.map(([, lat]) => lat);
  return [
    Math.min(...lngs), Math.min(...lats),
    Math.max(...lngs), Math.max(...lats),
  ];
}
