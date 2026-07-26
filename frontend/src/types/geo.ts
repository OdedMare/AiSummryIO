/**
 * Geometry types for the map picker, ported from LocatoAI's `geo-query.ts`.
 *
 * Only the drawing subset is kept: AiSummryIO scopes a summary by an area,
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

export function bboxForPolygon(geometry: GeoJSONPolygon): BBox {
  const points = geometry.coordinates.flat();
  const lngs = points.map(([lng]) => lng);
  const lats = points.map(([, lat]) => lat);
  return [
    Math.min(...lngs), Math.min(...lats),
    Math.max(...lngs), Math.max(...lats),
  ];
}
