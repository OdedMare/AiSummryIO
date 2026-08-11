import { Send } from "lucide-react";
import MapWorkspace from "@/components/MapWorkspace";
import type { AppShellController } from "./useAppShell";
import { isActive } from "./useAppShell";

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
      <SendAreaButton app={app} />
    </aside>
  );
}

/**
 * Submits straight from the map: drawing the last area is usually the step
 * before asking, and without this the user has to scroll back down to the
 * composer's Send button to submit the parts they just drew. It reuses
 * `app.ask`, the same path `submit` and the suggested-question chips use, so
 * it still passes identifier detection and the busy guard — this is a
 * shortcut into that path, not a second one. `MapPanel` only renders before a
 * conversation exists. The drawn area is valid scope by itself, so only an
 * empty selection or an in-flight request disables this shortcut.
 */
function SendAreaButton({ app }: { app: AppShellController }) {
  const disabled = app.submitting || isActive(app.run) || !app.geometry.length;
  return (
    <button type="button" className="primary-button map-panel-send"
      disabled={disabled} onClick={() => app.ask(app.message)}>
      <Send size={16} aria-hidden="true" /> שליחה עם האזור שסומן
    </button>
  );
}
