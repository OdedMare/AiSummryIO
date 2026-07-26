"use client";

import { useState } from "react";
import { MapContainer, TileLayer, ZoomControl } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";
import MapGeoms from "./MapGeoms";
import { DEFAULT_CENTER, DEFAULT_ZOOM, LAYERS } from "./consts";
import type { BBox, GeographyMode, GeoJSONPolygon } from "@/types/geo";

export interface LeafletMapProps {
  mode: GeographyMode;
  drawnGeometry: GeoJSONPolygon | null;
  /** Called when the user finishes drawing a polygon or rectangle. */
  onGeometryDrawn: (geometry: GeoJSONPolygon, bbox: BBox) => void;
  disabled?: boolean;
}

export default function LeafletMap({
  mode,
  drawnGeometry,
  onGeometryDrawn,
  disabled,
}: LeafletMapProps) {
  const [activeLayerId, setActiveLayerId] = useState(LAYERS[0].id);
  const layer = LAYERS.find((item) => item.id === activeLayerId) ?? LAYERS[0];

  return (
    <MapContainer
      center={[DEFAULT_CENTER[1], DEFAULT_CENTER[0]]}
      zoom={DEFAULT_ZOOM}
      className="picker-leaflet-map"
      zoomControl={false}
      minZoom={5}
      maxZoom={19}
      worldCopyJump={false}
    >
      <TileLayer
        key={layer.id}
        url={layer.url}
        attribution={layer.attribution}
        maxZoom={layer.maxZoom}
      />
      <MapGeoms
        mode={disabled ? "none" : mode}
        value={drawnGeometry}
        onChange={onGeometryDrawn}
      />
      <ZoomControl position="bottomleft" />
      <div className="picker-layer-switch">
        {LAYERS.map((option) => (
          <button
            key={option.id}
            type="button"
            className={option.id === activeLayerId ? "is-active" : ""}
            aria-pressed={option.id === activeLayerId}
            onClick={() => setActiveLayerId(option.id)}
          >
            {option.name}
          </button>
        ))}
      </div>
    </MapContainer>
  );
}
