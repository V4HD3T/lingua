import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getReviewQueue, submitReview } from "../api/review";
import { useSpeechSynthesis } from "../hooks/useSpeechSynthesis";
import { SpeakerButton } from "../components/SpeakerButton";
import { AchievementToast } from "../components/AchievementToast";
import { LoadingState, ErrorState } from "../components/StatusMessage";
import type { Achievement, ReviewQueueItem } from "../types";
import styles from "./ReviewPage.module.css";

// Simplified 3-button rating, mapped onto SM-2's 0-5 quality scale.
const RATINGS = [
  { label: "Again", quality: 1, className: "again" },
  { label: "Good", quality: 3, className: "good" },
  { label: "Easy", quality: 5, className: "easy" },
] as const;

export function ReviewPage() {
  const [queue, setQueue] = useState<ReviewQueueItem[] | null>(null);
  const [index, setIndex] = useState(0);
  const [isRevealed, setIsRevealed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sessionAchievements, setSessionAchievements] = useState<Achievement[]>([]);

  const voice = useSpeechSynthesis();

  useEffect(() => {
    getReviewQueue()
      .then(setQueue)
      .catch(() => setError("Something went wrong loading your review queue."));
  }, []);

  const currentItem = queue?.[index];

  async function handleRate(quality: number) {
    if (!currentItem || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const result = await submitReview(currentItem.vocabulary_item_id, quality);
      if (result.new_achievements.length > 0) {
        setSessionAchievements((prev) => [...prev, ...result.new_achievements]);
      }
      setIndex((prev) => prev + 1);
      setIsRevealed(false);
    } catch {
      setError("Something went wrong saving your answer.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className={styles.page}>
      <h1>Review</h1>
      <p className={styles.subtitle}>
        Words come back right when you're about to forget them — that's the
        whole idea behind spaced repetition.
      </p>

      {error && <ErrorState message={error} />}
      {!error && !queue && <LoadingState label="Loading your review queue" />}

      {queue && queue.length === 0 && (
        <div className={styles.emptyState}>
          <p>No words due for review right now.</p>
          <Link to="/courses" className={styles.browseLink}>
            Browse courses to learn new words →
          </Link>
        </div>
      )}

      {queue && queue.length > 0 && !currentItem && (
        <div className={styles.emptyState}>
          <p className={styles.doneHeadline}>All caught up ✓</p>
          <p>You reviewed {queue.length} word{queue.length === 1 ? "" : "s"}.</p>
          <Link to="/progress" className={styles.browseLink}>
            See your progress →
          </Link>
          <AchievementToast achievements={sessionAchievements} />
        </div>
      )}

      {currentItem && (
        <>
          <p className={styles.progressLabel}>
            {index + 1} / {queue!.length}
            {currentItem.is_new && <span className={styles.newBadge}>new</span>}
          </p>

          <div className={styles.card}>
            <div className={styles.cardWord}>
              {currentItem.word}
              {voice.isSupported && (
                <SpeakerButton
                  isSpeaking={voice.isSpeaking}
                  onClick={() => voice.speak(currentItem.word, currentItem.language_code)}
                  title={`Listen to "${currentItem.word}"`}
                />
              )}
            </div>

            {isRevealed ? (
              <>
                <p className={styles.cardTranslation}>{currentItem.translation}</p>
                {currentItem.example_sentence && (
                  <p className={styles.cardExample}>{currentItem.example_sentence}</p>
                )}
              </>
            ) : (
              <button
                type="button"
                className={styles.revealButton}
                onClick={() => setIsRevealed(true)}
              >
                Show answer
              </button>
            )}
          </div>

          {isRevealed && (
            <div className={styles.ratingRow}>
              <p className={styles.ratingPrompt}>How well did you know it?</p>
              <div className={styles.ratingButtons}>
                {RATINGS.map((rating) => (
                  <button
                    key={rating.label}
                    type="button"
                    className={`${styles.ratingButton} ${styles[rating.className]}`}
                    onClick={() => handleRate(rating.quality)}
                    disabled={isSubmitting}
                  >
                    {rating.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
