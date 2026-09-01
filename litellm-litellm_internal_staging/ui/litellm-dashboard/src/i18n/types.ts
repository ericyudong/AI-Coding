export type Locale = "en" | "zh";

export const LOCALE_STORAGE_KEY = "litellm_ui_locale";

export type TranslateParams = Record<string, string | number>;

export type { MessageKey } from "./locales/en";
export type Messages = Record<import("./locales/en").MessageKey, string>;
