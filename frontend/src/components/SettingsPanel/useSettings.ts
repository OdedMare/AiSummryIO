"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/services/api";

export type SettingsSection = "agent" | "flapi" | "database" | "limits";

const MASKED = "********";

export function useSettings() {
  const [activeSection, setActiveSection] =
    useState<SettingsSection>("agent");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [modelsError, setModelsError] = useState("");

  useEffect(() => {
    api.adminSession()
      .then(() => api.settings())
      .then((next) => { setValues(next); setAuthorized(true); })
      .catch(() => setAuthorized(false))
      .finally(() => setLoading(false));
  }, []);

  const save = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError(""); setMessage("");
    try {
      setValues(await api.updateSettings(values));
      setMessage("ההגדרות נשמרו ומוחלות על הקריאה הבאה.");
    } catch (reason) {
      setError(errorMessage(reason, "השמירה נכשלה"));
    } finally {
      setSaving(false);
    }
  };

  const loadModels = async () => {
    setLoadingModels(true); setModelsError("");
    try {
      setModels((await api.models()).models);
    } catch (reason) {
      setModelsError(errorMessage(reason, "טעינת המודלים נכשלה"));
    } finally {
      setLoadingModels(false);
    }
  };

  const set = (key: string, value: unknown) =>
    setValues((current) => ({ ...current, [key]: value }));
  const text = (key: string) => String(values[key] ?? "");
  const checked = (key: string) => Boolean(values[key]);
  const secretSaved = (key: string) => values[key] === MASKED;

  return {
    activeSection, setActiveSection, loading, saving, message, error,
    authorized, models, loadingModels, modelsError,
    save, loadModels, set, text, checked, secretSaved,
  };
}

export type SettingsController = ReturnType<typeof useSettings>;

function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}
