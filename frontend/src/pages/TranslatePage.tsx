import { useCallback, useEffect, useRef, useState } from "react";
import { listLanguages, translateText } from "../api/translate";
import { useAuth } from "../context/AuthContext";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { MicButton } from "../components/MicButton";
import type { Language } from "../types";
import styles from "./TranslatePage.module.css";

const DEBOUNCE_MS = 400;

export function TranslatePage() {
  const { user } = useAuth();
  const [languages, setLanguages] = useState<Language[]>([]);
  const [sourceLang, setSourceLang] = useState("en");
  const [targetLang, setTargetLang] = useState("es");
  const [sourceText, setSourceText] = useState("");
  const [translatedText, setTranslatedText] = useState("");
  const [isTranslating, setIsTranslating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const requestIdRef = useRef(0);

  const speech = useSpeechRecognition();

  useEffect(() => {
    listLanguages()
      .then(setLanguages)
      .catch(() => setLanguages([]));
  }, []);

  const runTranslation = useCallback(
    (text: string, from: string, to: string) => {
      if (!text.trim()) {
        setTranslatedText("");
        setIsTranslating(false);
        return;
      }

      const currentRequestId = ++requestIdRef.current;
      setIsTranslating(true);
      setError(null);

      translateText(text, from, to)
        .then((result) => {
          if (currentRequestId !== requestIdRef.current) return; // stale response, ignore
          setTranslatedText(result.translated_text);
          setSavedNotice(Boolean(user));
        })
        .catch(() => {
          if (currentRequestId !== requestIdRef.current) return;
          setError("Something went wrong while translating. Please try again.");
        })
        .finally(() => {
          if (currentRequestId !== requestIdRef.current) return;
          setIsTranslating(false);
        });
    },
    [user]
  );

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      runTranslation(sourceText, sourceLang, targetLang);
    }, DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceText, sourceLang, targetLang]);

  function handleSwap() {
    setSourceLang(targetLang);
    setTargetLang(sourceLang);
    setSourceText(translatedText);
    setTranslatedText(sourceText);
  }

  async function handleMicClick() {
    try {
      const transcript = await speech.listen(sourceLang);
      setSourceText((prev) => (prev ? `${prev} ${transcript}` : transcript));
    } catch {
      // the error is already surfaced via speech.error, nothing more to do here
    }
  }

  function languageName(code: string): string {
    return languages.find((l) => l.code === code)?.name ?? code;
  }

  return (
    <div className={styles.page}>
      <div className={styles.intro}>
        <h1>Say it your way, we'll handle the language</h1>
        <p className={styles.subtitle}>
          Translated the moment you finish typing. Built on a transformer-based
          model that supports 200+ languages.
        </p>
      </div>

      <div className={styles.panel}>
        <div className={styles.langBar}>
          <select
            className={styles.langSelect}
            value={sourceLang}
            onChange={(e) => setSourceLang(e.target.value)}
            aria-label="Source language"
          >
            {languages.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.name}
              </option>
            ))}
          </select>

          <button
            type="button"
            className={styles.swapButton}
            onClick={handleSwap}
            aria-label="Swap languages"
            title="Swap languages"
          >
            ⇄
          </button>

          <select
            className={styles.langSelect}
            value={targetLang}
            onChange={(e) => setTargetLang(e.target.value)}
            aria-label="Target language"
          >
            {languages.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.name}
              </option>
            ))}
          </select>
        </div>

        <div className={styles.grid}>
          <div className={styles.column}>
            <textarea
              className={styles.textarea}
              placeholder={`Type or say something in ${languageName(sourceLang)}...`}
              value={sourceText}
              onChange={(e) => setSourceText(e.target.value)}
              rows={8}
            />
            {speech.isSupported && (
              <div className={styles.micWrapper}>
                <MicButton isListening={speech.isListening} onClick={handleMicClick} />
              </div>
            )}
          </div>

          <div className={styles.column}>
            <div className={styles.output}>
              {isTranslating && sourceText.trim() ? (
                <span className={styles.placeholder}>translating...</span>
              ) : translatedText ? (
                translatedText
              ) : (
                <span className={styles.placeholder}>
                  Your translation will appear here
                </span>
              )}
            </div>
          </div>
        </div>

        {(error || speech.error) && (
          <p className={styles.errorText}>{error ?? speech.error}</p>
        )}

        <div className={styles.footerRow}>
          {savedNotice && !error ? (
            <span className={styles.savedNotice}>Saved to your translation history</span>
          ) : (
            !user && (
              <span className={styles.hint}>
                Log in to save your translations
              </span>
            )
          )}
        </div>
      </div>
    </div>
  );
}
