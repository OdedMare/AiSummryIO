"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, ZoomControl, useMap } from "react-leaflet";
// Leaflet's stylesheets are imported in `app/layout.tsx` so they load before
// `globals.css`; importing them here would put them after it again.
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

/**
 * Leaflet caches its container size at init. Inside the composer that size can
 * be measured while the box is still collapsed or hidden behind a modal, which
 * leaves the map rendering at the wrong width. Re-measure whenever the
 * container actually resizes.
 */
function SyncMapSize() {
  const map = useMap();

  useEffect(() => {
    const container = map.getContainer();
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(container);
    // Catch the first paint, before any resize has fired.
    map.invalidateSize();
    return () => observer.disconnect();
  }, [map]);

  return null;
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
      <SyncMapSize />
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
