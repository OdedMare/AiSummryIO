"use client";

import dynamic from "next/dynamic";
import { Hexagon, MapPin, Square, Trash2, Undo2 } from "lucide-react";
import { bboxForParts } from "@/types/geo";
import type { BBox, GeographyMode, GeoJSONPolygon } from "@/types/geo";

// Leaflet touches `window` at import time, so it must only load on the client.
const LeafletMap = dynamic(() => import("./LeafletMap"), {
  ssr: false,
  loading: () => <div className="picker-map-loading">המפה נטענת…</div>,
});

// The hints name the accumulating behavior: the tool stays armed after a
// shape closes, and nothing tells the user that the next drawing adds an
// area rather than replacing the one they just drew.
const DRAW_HINTS: Partial<Record<GeographyMode, string>> = {
  polygon: "לחצו על נקודות לציור · לסיום לחצו על הנקודה הראשונה · ניתן לצייר כמה אזורים",
  rectangle: "לחצו וגררו כדי לצייר מלבן · ניתן לצייר כמה אזורים",
};

interface MapWorkspaceProps {
  mode: GeographyMode;
  /** Every part drawn so far; they travel as one MultiPolygon. */
  geometry: GeoJSONPolygon[];
  onModeChange: (mode: GeographyMode) => void;
  onGeometryDrawn: (geometry: GeoJSONPolygon, bbox: BBox) => void;
  /** Removes the most recently drawn part. */
  onUndo: () => void;
  onClear: () => void;
  disabled?: boolean;
}

function formatBbox(bbox: BBox): string {
  return bbox.map((value) => value.toFixed(4)).join(", ");
}

/**
 * Small map picker for the composer: draw one area, send it as the request's
 * geographic scope. A trimmed port of LocatoAI's `MapWorkspace`.
 */
export default function MapWorkspace({
  mode,
  geometry,
  onModeChange,
  onGeometryDrawn,
  onUndo,
  onClear,
  disabled,
}: MapWorkspaceProps) {
  const hint = disabled ? undefined : DRAW_HINTS[mode];
  const bbox = bboxForParts(geometry);

  return (
    <div className="map-picker">
      <div className="map-picker-tools" role="group" aria-label="כלי שרטוט">
        <button
          type="button"
          className={mode === "polygon" ? "is-active" : ""}
          aria-pressed={mode === "polygon"}
          disabled={disabled}
          onClick={() => onModeChange(mode === "polygon" ? "none" : "polygon")}
        >
          <Hexagon size={14} aria-hidden="true" /> פוליגון
        </button>
        <button
          type="button"
          className={mode === "rectangle" ? "is-active" : ""}
          aria-pressed={mode === "rectangle"}
          disabled={disabled}
          onClick={() =>
            onModeChange(mode === "rectangle" ? "none" : "rectangle")
          }
        >
          <Square size={14} aria-hidden="true" /> מלבן
        </button>
        <button
          type="button"
          disabled={disabled || !geometry.length}
          onClick={onUndo}
        >
          <Undo2 size={14} aria-hidden="true" /> ביטול אזור אחרון
        </button>
        <button
          type="button"
          className="map-picker-clear"
          disabled={disabled || !geometry.length}
          onClick={onClear}
        >
          <Trash2 size={14} aria-hidden="true" /> ניקוי הכל
        </button>
      </div>

      <div className="map-picker-canvas">
        <LeafletMap
          mode={mode}
          drawnGeometry={geometry}
          onGeometryDrawn={onGeometryDrawn}
          disabled={disabled}
        />
        {hint && <p className="map-picker-hint">{hint}</p>}
      </div>

      <p className="map-picker-status" role="status">
        <MapPin size={13} aria-hidden="true" />
        {bbox ? (
          <>
            {geometry.length === 1
              ? "נבחר אזור אחד"
              : `נבחרו ${geometry.length} אזורים`}{" "}
            · <span dir="ltr">{formatBbox(bbox)}</span>
          </>
        ) : (
          "לא נבחר אזור — הסיכום יופק לפי המזהה בלבד"
        )}
      </p>
    </div>
  );
}
