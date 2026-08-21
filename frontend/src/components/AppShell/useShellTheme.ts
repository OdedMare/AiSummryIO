import type { Dispatch, SetStateAction } from "react";
import { useEffect } from "react";

type Setter<T> = Dispatch<SetStateAction<T>>;

export function useInitialData(
  setDark: Setter<boolean>,
) {
  useEffect(() => {
    const saved = window.localStorage.getItem("aisummry-theme");
    const dark = saved
      ? saved === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    window.setTimeout(() => setDark(dark), 0);
  }, [setDark]);
}

export function useTheme(dark: boolean) {
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    window.localStorage.setItem("aisummry-theme", dark ? "dark" : "light");
  }, [dark]);
}
