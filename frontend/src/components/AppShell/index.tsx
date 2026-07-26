"use client";

import AgentStudioPanel from "@/components/AgentStudioPanel";
import SettingsPanel from "@/components/SettingsPanel";
import SummaryWorkspace from "@/components/SummaryWorkspace";
import Composer from "./Composer";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import { useAppShell } from "./useAppShell";

export default function AppShell() {
  const app = useAppShell();
  return (
    <div className="app-shell">
      <Sidebar app={app} />
      <section className="conversation-shell">
        <Topbar app={app} />
        <SummaryWorkspace run={app.run} skills={app.skills}
          selectedSkillKeys={app.selectedSkillKeys}
          onToggleSkill={app.toggleSkill} />
        <Composer app={app} />
      </section>
      {app.settingsOpen &&
        <SettingsPanel onClose={() => app.setSettingsOpen(false)} />}
      {app.studioOpen &&
        <AgentStudioPanel onClose={() => app.setStudioOpen(false)} />}
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
