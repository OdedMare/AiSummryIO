import type { Dispatch, SetStateAction } from "react";
import { useEffect } from "react";
import { api } from "@/services/api";
import type { SummarySkill } from "@/types";

type Setter<T> = Dispatch<SetStateAction<T>>;

export function useInitialData(
  loadHistory: () => void,
  setDark: Setter<boolean>,
  setSkills: Setter<SummarySkill[]>,
) {
  useEffect(() => {
    const saved = window.localStorage.getItem("aisummry-theme");
    const dark = saved
      ? saved === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    window.setTimeout(() => setDark(dark), 0);
    loadHistory();
    api.skills().then(setSkills).catch(() => undefined);
  }, [loadHistory, setDark, setSkills]);
}

export function useTheme(dark: boolean) {
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    window.localStorage.setItem("aisummry-theme", dark ? "dark" : "light");
  }, [dark]);
}
