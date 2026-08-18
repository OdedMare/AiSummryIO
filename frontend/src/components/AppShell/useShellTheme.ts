import type { Dispatch, SetStateAction } from "react";
import { useEffect } from "react";
import { api } from "@/services/api";
import type { SummaryAgent, SummarySkill } from "@/types";

type Setter<T> = Dispatch<SetStateAction<T>>;

export function useInitialData(
  setDark: Setter<boolean>,
  setSkills: Setter<SummarySkill[]>,
  setAgents: Setter<SummaryAgent[]>,
) {
  useEffect(() => {
    const saved = window.localStorage.getItem("aisummry-theme");
    const dark = saved
      ? saved === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    window.setTimeout(() => setDark(dark), 0);
    api.skills().then(setSkills).catch(() => undefined);
    api.specialists().then(setAgents).catch(() => undefined);
  }, [setAgents, setDark, setSkills]);
}

export function useTheme(dark: boolean) {
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    window.localStorage.setItem("aisummry-theme", dark ? "dark" : "light");
  }, [dark]);
}
