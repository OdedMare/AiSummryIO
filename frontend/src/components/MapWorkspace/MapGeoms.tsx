import { useEffect, useRef } from "react";
import L from "leaflet";
import { FeatureGroup, GeoJSON, useMap } from "react-leaflet";
import { EditControl } from "react-leaflet-draw";
import { bboxForPolygon } from "@/types/geo";
import type { BBox, GeographyMode, GeoJSONPolygon } from "@/types/geo";

interface MapGeomsProps {
  mode: GeographyMode;
  /** Every part drawn so far; they travel as one MultiPolygon. */
  value: GeoJSONPolygon[];
  onChange: (geometry: GeoJSONPolygon, bbox: BBox) => void;
}

const SHAPE = { color: "#d97757", fillColor: "#d97757", fillOpacity: 0.3 };

/** Draws the active shape tool and reports the finished polygon upward. */
export default function MapGeoms({ mode, value, onChange }: MapGeomsProps) {
  const featureGroupRef = useRef<L.FeatureGroup>(null);
  const activeDrawRef = useRef<L.Draw.Feature | null>(null);
  const map = useMap();

  useEffect(() => {
    featureGroupRef.current?.clearLayers();

    activeDrawRef.current?.disable();
    activeDrawRef.current = null;

    // leaflet-draw's published types incorrectly model its augmented Map as a
    // subclass. At runtime this is the same Leaflet map instance.
    const drawMap = map as unknown as L.DrawMap;

    if (mode === "polygon") {
      activeDrawRef.current = new L.Draw.Polygon(drawMap, {
        allowIntersection: false,
        showArea: true,
        shapeOptions: SHAPE,
      });
    } else if (mode === "rectangle") {
      activeDrawRef.current = new L.Draw.Rectangle(drawMap, {
        shapeOptions: SHAPE,
      });
    }

    activeDrawRef.current?.enable();

    return () => {
      activeDrawRef.current?.disable();
      activeDrawRef.current = null;
    };
  }, [map, mode]);

  const handleCreated = (event: L.DrawEvents.Created) => {
    const feature = (event.layer as L.Polygon).toGeoJSON() as
      GeoJSON.Feature<GeoJSON.Polygon>;
    if (feature.geometry.type !== "Polygon") return;

    const geometry = feature.geometry as GeoJSONPolygon;
    // The finished shape is dropped from the draw group and re-rendered below
    // as part of `value`. Leaving it here would paint it twice, and the group
    // is cleared per draw session rather than per accumulated part.
    featureGroupRef.current?.clearLayers();
    onChange(geometry, bboxForPolygon(geometry));

    // leaflet-draw disarms itself once a shape closes. Re-arming keeps the
    // tool live so the next part is drawn without reselecting the tool.
    activeDrawRef.current?.enable();
  };

  const drawEnabled = mode === "polygon" || mode === "rectangle";

  return (
    <>
      <FeatureGroup ref={featureGroupRef}>
        {drawEnabled && (
          <EditControl
            position="bottomleft"
            onCreated={handleCreated}
            edit={{ edit: false, remove: false }}
            draw={{
              marker: false,
              polyline: false,
              circle: false,
              circlemarker: false,
              polygon:
                mode === "polygon"
                  ? {
                      allowIntersection: false,
                      showArea: true,
                      shapeOptions: SHAPE,
                    }
                  : false,
              rectangle:
                mode === "rectangle" ? { shapeOptions: SHAPE } : false,
            }}
          />
        )}
      </FeatureGroup>
      {value.map((part, index) => (
        <GeoJSON
          // Keyed by index as well as extent: two parts can share a bbox, and
          // a stale key would leave a removed part painted on the map.
          key={`${index}-${JSON.stringify(bboxForPolygon(part))}`}
          data={part}
          style={SHAPE}
        />
      ))}
    </>
  );
}
