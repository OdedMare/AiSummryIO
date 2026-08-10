import { Send } from "lucide-react";
import MapWorkspace from "@/components/MapWorkspace";
import type { GeoJSONPolygon } from "@/types/geo";
import type { AppShellController } from "./useAppShell";
import { isActive } from "./useAppShell";

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
      <SendAreaButton app={app} />
    </aside>
  );
}

/**
 * Submits straight from the map: drawing an area is usually the last step
 * before asking, and without this the user has to scroll back down to the
 * composer's Send button to submit the polygon they just drew. It reuses
 * `app.ask`, the same path `submit` and the suggested-question chips use, so
 * it still passes identifier detection and the busy guard — this is a
 * shortcut into that path, not a second one. `MapPanel` only renders before
 * a conversation exists, so the disabled check mirrors the composer's
 * new-conversation branch, plus a drawn area is what this button is for.
 */
function SendAreaButton({ app }: { app: AppShellController }) {
  const disabled = app.submitting || isActive(app.run) || !app.geometry ||
    (!app.rootId.trim() && !app.message.trim());
  return (
    <button type="button" className="primary-button map-panel-send"
      disabled={disabled} onClick={() => app.ask(app.message)}>
      <Send size={16} aria-hidden="true" /> שליחה עם האזור שסומן
    </button>
  );
}
