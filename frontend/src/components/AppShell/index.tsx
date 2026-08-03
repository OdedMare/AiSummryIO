"use client";

import AgentStudioPanel from "@/components/AgentStudioPanel";
import SettingsPanel from "@/components/SettingsPanel";
import SummaryWorkspace from "@/components/SummaryWorkspace";
import Composer from "./Composer";
import MapPanel from "./MapPanel";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import { useAppShell } from "./useAppShell";

export default function AppShell() {
  const app = useAppShell();
  // The studio takes the whole viewport rather than floating over the shell:
  // its forms and interviews need the height, and a dialog could only ever
  // lend them a fraction of it.
  if (app.studioOpen) {
    return <AgentStudioPanel onClose={() => app.setStudioOpen(false)} />;
  }
  return (
    <div className={`app-shell${app.conversation ? "" : " has-map"}`}>
      <Sidebar app={app} />
      <section className="conversation-shell">
        <Topbar app={app} />
        <SummaryWorkspace runs={app.runs} run={app.run} skills={app.skills} />
        <Composer app={app} />
      </section>
      {!app.conversation && <MapPanel app={app} />}
      {app.settingsOpen &&
        <SettingsPanel onClose={() => app.setSettingsOpen(false)} />}
      {app.sidebarOpen && <Backdrop app={app} />}
    </div>
  );
}

function Backdrop({ app }: { app: ReturnType<typeof useAppShell> }) {
  return (
    <button className="sidebar-backdrop" type="button"
      onClick={() => app.setSidebarOpen(false)} aria-label="סגירת תפריט" />
  );
}
