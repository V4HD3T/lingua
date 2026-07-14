import { useCallback, useEffect, useRef, useState } from "react";
import type { SpeechRecognitionInstance } from "../types/speech";
import { toSpeechLang } from "../utils/speechLang";

const RecognitionCtor: (new () => SpeechRecognitionInstance) | undefined =
  typeof window !== "undefined"
    ? window.SpeechRecognition ?? window.webkitSpeechRecognition
    : undefined;

interface UseSpeechRecognitionResult {
  /** Whether the browser supports the Web Speech API (Chrome/Edge; not in Firefox). */
  isSupported: boolean;
  isListening: boolean;
  error: string | null;
  /** Starts listening, returns a Promise that resolves with a single result. */
  listen: (langCode: string) => Promise<string>;
  stop: () => void;
}

/** Wraps the browser's built-in speech recognition API. Doesn't send audio
 * to a server and doesn't download a model — runs entirely client-side. */
export function useSpeechRecognition(): UseSpeechRecognitionResult {
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  const isSupported = Boolean(RecognitionCtor);

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  const listen = useCallback((langCode: string): Promise<string> => {
    return new Promise((resolve, reject) => {
      if (!RecognitionCtor) {
        const message = "Your browser doesn't support speech recognition.";
        setError(message);
        reject(new Error(message));
        return;
      }

      const recognition = new RecognitionCtor();
      recognition.lang = toSpeechLang(langCode);
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setError(null);
        setIsListening(true);
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0]?.[0]?.transcript ?? "";
        resolve(transcript);
      };

      recognition.onerror = (event) => {
        const message =
          event.error === "not-allowed" || event.error === "permission-denied"
            ? "Microphone permission was denied."
            : event.error === "no-speech"
              ? "I didn't catch that — want to try again?"
              : "Something went wrong recognizing speech.";
        setError(message);
        reject(new Error(message));
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    });
  }, []);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  return { isSupported, isListening, error, listen, stop };
}
