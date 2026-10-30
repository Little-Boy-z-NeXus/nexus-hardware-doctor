/* eslint-disable react-refresh/only-export-components -- provider and hook intentionally share one module */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Language = "en" | "vi";

const STORAGE_KEY = "nexus.language";

interface I18nContextValue {
  language: Language;
  locale: "en-US" | "vi-VN";
  setLanguage: (language: Language) => void;
  text: (english: string, vietnamese: string) => string;
}

const I18nContext = createContext<I18nContextValue>({
  language: "en",
  locale: "en-US",
  setLanguage: () => undefined,
  text: (english) => english,
});

function initialLanguage(): Language {
  if (typeof window === "undefined") return "en";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "vi" || stored === "en" ? stored : "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(initialLanguage);

  const setLanguage = (nextLanguage: Language) => {
    setLanguageState(nextLanguage);
    window.localStorage.setItem(STORAGE_KEY, nextLanguage);
  };

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const value = useMemo<I18nContextValue>(() => ({
    language,
    locale: language === "vi" ? "vi-VN" : "en-US",
    setLanguage,
    text: (english, vietnamese) => language === "vi" ? vietnamese : english,
  }), [language]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}
