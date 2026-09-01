"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import en from "./locales/en";
import zh from "./locales/zh";
import {
  LOCALE_STORAGE_KEY,
  type Locale,
  type MessageKey,
  type Messages,
  type TranslateParams,
} from "./types";

const catalogs: Record<Locale, Messages> = {
  en: en as Messages,
  zh,
};

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey, params?: TranslateParams) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

function interpolate(template: string, params?: TranslateParams): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, name: string) =>
    params[name] === undefined || params[name] === null ? `{${name}}` : String(params[name]),
  );
}

function detectInitialLocale(): Locale {
  if (typeof window === "undefined") return "zh";
  const saved = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  if (saved === "en" || saved === "zh") return saved;
  const lang = window.navigator.language?.toLowerCase() ?? "";
  return lang.startsWith("zh") ? "zh" : "en";
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => detectInitialLocale());
  const [ready, setReady] = useState(typeof window !== "undefined");

  useEffect(() => {
    setLocaleState(detectInitialLocale());
    setReady(true);
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, next);
    } catch {
      // ignore storage failures
    }
    if (typeof document !== "undefined") {
      document.documentElement.lang = next === "zh" ? "zh-CN" : "en";
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  }, [locale, ready]);

  const t = useCallback(
    (key: MessageKey, params?: TranslateParams) => {
      const dict = catalogs[locale] ?? catalogs.en;
      const template = dict[key] ?? catalogs.en[key] ?? key;
      return interpolate(template, params);
    },
    [locale],
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return ctx;
}
