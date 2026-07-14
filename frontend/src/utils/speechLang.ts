const SPEECH_LANG_MAP: Record<string, string> = {
  tr: "tr-TR",
  en: "en-US",
  de: "de-DE",
  fr: "fr-FR",
  es: "es-ES",
  ar: "ar-SA",
  ru: "ru-RU",
  ja: "ja-JP",
  zh: "zh-CN",
};

/** Maps the app's short language code ("en") to the BCP-47 code the Web
 * Speech API expects ("en-US"). Falls back to the code as-is if there's no
 * mapping. */
export function toSpeechLang(code: string): string {
  return SPEECH_LANG_MAP[code] ?? code;
}
