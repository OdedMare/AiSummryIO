import { useEffect, useRef } from "react";
import L from "leaflet";
import { FeatureGroup, GeoJSON, useMap } from "react-leaflet";
import { EditControl } from "react-leaflet-draw";
import { bboxForPolygon } from "@/types/geo";
import type { BBox, GeographyMode, GeoJSONPolygon } from "@/types/geo";

interface MapGeomsProps {
  mode: GeographyMode;
  value: GeoJSONPolygon | null;
  onChange: (geometry: GeoJSONPolygon, bbox: BBox) => void;
}

const SHAPE = { color: "#7455e9", fillColor: "#7455e9", fillOpacity: 0.3 };

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
    featureGroupRef.current?.clearLayers();
    onChange(geometry, bboxForPolygon(geometry));
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
      {value && (
        <GeoJSON
          key={JSON.stringify(bboxForPolygon(value))}
          data={value}
          style={SHAPE}
        />
      )}
    </>
  );
}
