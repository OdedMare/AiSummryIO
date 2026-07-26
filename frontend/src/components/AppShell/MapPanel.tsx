import MapWorkspace from "@/components/MapWorkspace";
import type { GeoJSONPolygon } from "@/types/geo";
import type { AppShellController } from "./useAppShell";

/**
 * The map lives in its own side panel rather than inside the composer: at
 * composer widths a usable drawing area made the form taller than the shell's
 * bottom row, which squeezed and clipped the conversation above it.
 */
export default function MapPanel({ app }: { app: AppShellController }) {
  const clear = () => { app.setGeometry(null); app.setGeoMode("none"); };
  const drawn = (geometry: GeoJSONPolygon) => {
    app.setGeometry(geometry); app.setGeoMode("none");
  };
  return (
    <aside className="map-panel" aria-label="אזור על המפה">
      <div className="map-panel-head">
        <h2>אזור על המפה</h2>
        <span>לא חובה</span>
      </div>
      <MapWorkspace mode={app.geoMode} geometry={app.geometry}
        onModeChange={app.setGeoMode} onGeometryDrawn={drawn}
        onClear={clear} disabled={app.submitting} />
    </aside>
  );
}
