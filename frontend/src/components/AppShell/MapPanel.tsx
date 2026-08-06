import MapWorkspace from "@/components/MapWorkspace";
import type { AppShellController } from "./useAppShell";

/**
 * The map lives in its own side panel rather than inside the composer: at
 * composer widths a usable drawing area made the form taller than the shell's
 * bottom row, which squeezed and clipped the conversation above it.
 */
export default function MapPanel({ app }: { app: AppShellController }) {
  // The mode deliberately survives a finished shape: several parts make one
  // MultiPolygon, and dropping back to "none" after each would force the user
  // to reselect the tool between the areas of a single scope.
  return (
    <aside className="map-panel" aria-label="אזור על המפה">
      <div className="map-panel-head">
        <h2>אזור על המפה</h2>
        <span>לא חובה</span>
      </div>
      <MapWorkspace mode={app.geoMode} geometry={app.geometry}
        onModeChange={app.setGeoMode} onGeometryDrawn={app.addGeometry}
        onUndo={app.undoGeometry} onClear={app.clearGeometry}
        disabled={app.submitting} />
    </aside>
  );
}
