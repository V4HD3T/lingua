import { useCallback, useEffect, useRef, useState } from "react";
import { detectLanguage, listLanguages, translateText } from "../api/translate";
import { useAuth } from "../context/AuthContext";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "../hooks/useSpeechSynthesis";
import { MicButton } from "../components/MicButton";
import { SpeakerButton } from "../components/SpeakerButton";
import { AchievementToast } from "../components/AchievementToast";
import type { Achievement, IdiomWarning, Language } from "../types";
import styles from "./TranslatePage.module.css";

const DEBOUNCE_MS = 400;
const AUTO_DETECT = "auto";

interface DetectedInfo {
  languageCode: string;
  isReliable: boolean;
}

export function TranslatePage() {
  const { user } = useAuth();
  const [languages, setLanguages] = useState<Language[]>([]);
  const [sourceLang, setSourceLang] = useState(AUTO_DETECT);
  const [targetLang, setTargetLang] = useState("es");
  const [sourceText, setSourceText] = useState("");
  const [translatedText, setTranslatedText] = useState("");
  const [confidence, setConfidence] = useState<number | null>(null);
  const [alternatives, setAlternatives] = useState<string[]>([]);
  const [idiomWarnings, setIdiomWarnings] = useState<IdiomWarning[]>([]);
  const [newAchievements, setNewAchievements] = useState<Achievement[]>([]);
  const [isTranslating, setIsTranslating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState(false);
  const [detected, setDetected] = useState<DetectedInfo | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const requestIdRef = useRef(0);

  const speech = useSpeechRecognition();
  const voice = useSpeechSynthesis();

  useEffect(() => {
    listLanguages()
      .then(setLanguages)
      .catch(() => setLanguages([]));
  }, []);

  const runTranslation = useCallback(
    async (text: string, from: string, to: string) => {
      if (!text.trim()) {
        setTranslatedText("");
        setConfidence(null);
        setAlternatives([]);
        setIdiomWarnings([]);
        setIsTranslating(false);
        setDetected(null);
        return;
      }

      const currentRequestId = ++requestIdRef.current;
      setIsTranslating(true);
      setError(null);

      try {
        let resolvedFrom = from;

        if (from === AUTO_DETECT) {
          const guess = await detectLanguage(text);
          if (currentRequestId !== requestIdRef.current) return; // stale response, ignore
          resolvedFrom = guess.language_code;
          setDetected({ languageCode: guess.language_code, isReliable: guess.is_reliable });
        } else {
          setDetected(null);
        }

        const result = await translateText(text, resolvedFrom, to);
        if (currentRequestId !== requestIdRef.current) return;
        setTranslatedText(result.translated_text);
        setConfidence(result.confidence);
        setAlternatives(result.alternatives.filter((a) => a !== result.translated_text));
        setIdiomWarnings(result.idiom_warnings);
        setNewAchievements(result.new_achievements);
        setSavedNotice(Boolean(user));
      } catch {
        if (currentRequestId !== requestIdRef.current) return;
        setError("Something went wrong while translating. Please try again.");
      } finally {
        if (currentRequestId === requestIdRef.current) setIsTranslating(false);
      }
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
    // Swapping out of auto-detect wouldn't make sense as a source language,
    // so lock in whatever was actually detected (or the target, as a fallback).
    const effectiveSource = sourceLang === AUTO_DETECT ? (detected?.languageCode ?? targetLang) : sourceLang;
    setSourceLang(targetLang);
    setTargetLang(effectiveSource);
    setSourceText(translatedText);
    setTranslatedText(sourceText);
  }

  async function handleMicClick() {
    try {
      const listenLang = sourceLang === AUTO_DETECT ? (detected?.languageCode ?? "en") : sourceLang;
      const transcript = await speech.listen(listenLang);
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
          <div className={styles.langSelectWrap}>
            <select
              className={styles.langSelect}
              value={sourceLang}
              onChange={(e) => setSourceLang(e.target.value)}
              aria-label="Source language"
            >
              <option value={AUTO_DETECT}>Detect language</option>
              {languages.map((lang) => (
                <option key={lang.code} value={lang.code}>
                  {lang.name}
                </option>
              ))}
            </select>
            {sourceLang === AUTO_DETECT && detected && (
              <span className={styles.detectedHint}>
                Detected: {languageName(detected.languageCode)}
                {!detected.isReliable && " (not sure — check this)"}
              </span>
            )}
          </div>

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
              placeholder={
                sourceLang === AUTO_DETECT
                  ? "Type or say something — I'll figure out the language..."
                  : `Type or say something in ${languageName(sourceLang)}...`
              }
              value={sourceText}
              onChange={(e) => setSourceText(e.target.value)}
              rows={8}
            />
            {speech.isSupported && (
              <div className={styles.cornerButtonWrapper}>
                <MicButton isListening={speech.isListening} onClick={handleMicClick} />
              </div>
            )}
            {idiomWarnings.length > 0 && (
              <div className={styles.idiomBox}>
                {idiomWarnings.map((warning) => (
                  <p key={warning.phrase} className={styles.idiomEntry}>
                    <strong>"{warning.phrase}"</strong> is idiomatic — {warning.note}
                  </p>
                ))}
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
            {voice.isSupported && translatedText && (
              <div className={styles.cornerButtonWrapper}>
                <SpeakerButton
                  isSpeaking={voice.isSpeaking}
                  onClick={() =>
                    voice.isSpeaking
                      ? voice.stop()
                      : voice.speak(translatedText, targetLang)
                  }
                  title="Listen to the translation"
                />
              </div>
            )}
            {translatedText && confidence !== null && (
              <div className={styles.confidenceRow}>
                <span
                  className={styles.confidenceBadge}
                  title="Mock translation service — this is an illustrative placeholder, not a real model confidence score. See CHANGELOG.md."
                >
                  {Math.round(confidence * 100)}% confidence
                </span>
                {alternatives.length > 0 && (
                  <span className={styles.alternativesInline}>
                    also: {alternatives.join(" · ")}
                  </span>
                )}
              </div>
            )}
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

      <AchievementToast achievements={newAchievements} />
    </div>
  );
}
