/** API language for `X-Orqestra-Lang` — set by LanguageProvider, read by api/client. */

export type AppLang = 'en' | 'de';

let _lang: AppLang = 'en';

export function setApiLanguage(lang: AppLang): void {
  _lang = lang;
}

export function getApiLanguage(): AppLang {
  return _lang;
}
