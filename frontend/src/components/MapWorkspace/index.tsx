"use client";

import dynamic from "next/dynamic";
import { Hexagon, MapPin, Square, Trash2 } from "lucide-react";
import { bboxForPolygon } from "@/types/geo";
import type { BBox, GeographyMode, GeoJSONPolygon } from "@/types/geo";

// Leaflet touches `window` at import time, so it must only load on the client.
const LeafletMap = dynamic(() => import("./LeafletMap"), {
  ssr: false,
  loading: () => <div className="picker-map-loading">המפה נטענת…</div>,
});

const DRAW_HINTS: Partial<Record<GeographyMode, string>> = {
  polygon: "לחצו על נקודות לציור · לסיום לחצו על הנקודה הראשונה",
  rectangle: "לחצו וגררו כדי לצייר מלבן",
};

interface MapWorkspaceProps {
  mode: GeographyMode;
  geometry: GeoJSONPolygon | null;
  onModeChange: (mode: GeographyMode) => void;
  onGeometryDrawn: (geometry: GeoJSONPolygon, bbox: BBox) => void;
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
  onClear,
  disabled,
}: MapWorkspaceProps) {
  const hint = disabled ? undefined : DRAW_HINTS[mode];

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
          className="map-picker-clear"
          disabled={disabled || !geometry}
          onClick={onClear}
        >
          <Trash2 size={14} aria-hidden="true" /> ניקוי
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
        {geometry ? (
          <>
            נבחר אזור ·{" "}
            <span dir="ltr">{formatBbox(bboxForPolygon(geometry))}</span>
          </>
        ) : (
          "לא נבחר אזור — הסיכום יופק לפי המזהה בלבד"
        )}
      </p>
    </div>
  );
}
