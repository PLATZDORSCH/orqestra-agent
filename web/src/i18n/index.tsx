import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { de } from './de';
import { en } from './en';
import type { TranslationKey } from './types';
import { setApiLanguage, type AppLang } from './apiLang';
import { api } from '../api/client';

const STORAGE_KEY = 'orq.ui.lang';

type Messages = Record<TranslationKey, string>;

const messages: Record<AppLang, Messages> = { en, de };

function readInitialLang(): AppLang {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === 'de' || v === 'en') return v;
  } catch {
    /* ignore */
  }
  if (typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('de')) {
    return 'de';
  }
  return 'en';
}

interface I18nContextValue {
  lang: AppLang;
  setLang: (lang: AppLang) => void;
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<AppLang>(() => readInitialLang());

  useEffect(() => {
    setApiLanguage(lang);
  }, [lang]);

  useEffect(() => {
    let cancelled = false;
    api
      .getUiSettings()
      .then((r) => {
        if (cancelled) return;
        try {
          if (localStorage.getItem(STORAGE_KEY)) return;
        } catch {
          /* ignore */
        }
        const l = r.language === 'de' ? 'de' : 'en';
        setLangState(l);
        setApiLanguage(l);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const setLang = useCallback((next: AppLang) => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
    setApiLanguage(next);
    void api.putUiSettings({ language: next }).catch(() => {});
  }, []);

  const t = useCallback(
    (key: TranslationKey, vars?: Record<string, string | number>) => {
      let s = messages[lang][key] ?? messages.en[key] ?? String(key);
      if (vars) {
        for (const [k, v] of Object.entries(vars)) {
          s = s.split(`{{${k}}}`).join(String(v));
        }
      }
      return s;
    },
    [lang],
  );

  const value = useMemo<I18nContextValue>(() => ({ lang, setLang, t }), [lang, setLang, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error('useI18n must be used within LanguageProvider');
  }
  return ctx;
}
