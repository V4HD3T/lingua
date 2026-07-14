import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getLesson, listVocabulary } from "../api/courses";
import { getQuizByLesson } from "../api/quizzes";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { MicButton } from "../components/MicButton";
import { LoadingState, ErrorState } from "../components/StatusMessage";
import type { Lesson, VocabularyItem } from "../types";
import styles from "./LessonDetailPage.module.css";

type PracticeStatus = "correct" | "incorrect";

interface PracticeState {
  status: PracticeStatus;
  heard?: string;
}

function normalize(text: string): string {
  return text.trim().toLowerCase();
}

export function LessonDetailPage() {
  const { lessonId } = useParams<{ lessonId: string }>();
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [vocabulary, setVocabulary] = useState<VocabularyItem[] | null>(null);
  const [hasQuiz, setHasQuiz] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [practice, setPractice] = useState<Record<number, PracticeState>>({});
  const [listeningItemId, setListeningItemId] = useState<number | null>(null);

  const speech = useSpeechRecognition();

  useEffect(() => {
    if (!lessonId) return;
    const id = Number(lessonId);

    getLesson(id)
      .then(setLesson)
      .catch(() => setError("Something went wrong loading this lesson."));

    listVocabulary(id)
      .then(setVocabulary)
      .catch(() => setError("Something went wrong loading the vocabulary."));

    getQuizByLesson(id)
      .then(() => setHasQuiz(true))
      .catch(() => setHasQuiz(false));
  }, [lessonId]);

  async function practiceWord(item: VocabularyItem) {
    if (!lesson) return;
    setListeningItemId(item.id);
    try {
      const transcript = await speech.listen(lesson.language_code);
      const isCorrect = normalize(transcript) === normalize(item.word);
      setPractice((prev) => ({
        ...prev,
        [item.id]: { status: isCorrect ? "correct" : "incorrect", heard: transcript },
      }));
    } catch {
      // the error is already surfaced via speech.error
    } finally {
      setListeningItemId(null);
    }
  }

  return (
    <div className={styles.page}>
      <Link to="/courses" className={styles.backLink}>
        ← Courses
      </Link>

      {error && <ErrorState message={error} />}
      {!error && !lesson && <LoadingState label="Loading lesson" />}

      {lesson && <h1>{lesson.title}</h1>}
      <p className={styles.sectionLabel}>Vocabulary</p>

      {speech.error && <p className={styles.speechError}>{speech.error}</p>}

      <div className={styles.vocabList}>
        {vocabulary?.map((item) => {
          const state = practice[item.id];
          return (
            <div key={item.id} className={styles.vocabCard}>
              <div className={styles.vocabHead}>
                <div>
                  <span className={styles.word}>{item.word}</span>
                  <span className={styles.translation}>{item.translation}</span>
                </div>
                {speech.isSupported && lesson && (
                  <MicButton
                    isListening={listeningItemId === item.id && speech.isListening}
                    onClick={() => practiceWord(item)}
                    disabled={listeningItemId !== null && listeningItemId !== item.id}
                    title={`Say the word "${item.word}"`}
                  />
                )}
              </div>
              {item.example_sentence && (
                <p className={styles.example}>{item.example_sentence}</p>
              )}
              {state && (
                <p
                  className={
                    state.status === "correct" ? styles.feedbackCorrect : styles.feedbackIncorrect
                  }
                >
                  {state.status === "correct"
                    ? "Nice pronunciation ✓"
                    : `I heard: "${state.heard}" — want to try again?`}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {hasQuiz && (
        <Link to={`/lessons/${lessonId}/quiz`} className={styles.quizButton}>
          Start quiz
        </Link>
      )}
    </div>
  );
}
