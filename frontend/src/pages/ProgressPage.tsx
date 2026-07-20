import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchMyStats } from "../api/stats";
import { getVocabularySuggestions } from "../api/suggestions";
import { getMyAchievements } from "../api/achievements";
import { updateDailyGoal } from "../api/auth";
import { LoadingState, ErrorState } from "../components/StatusMessage";
import type { Achievement, UserStats, VocabularySuggestion } from "../types";
import { useToast } from "../context/ToastContext";
import styles from "./ProgressPage.module.css";

export function ProgressPage() {
  const toast = useToast();
  const [stats, setStats] = useState<UserStats | null>(null);
  const [suggestions, setSuggestions] = useState<VocabularySuggestion[] | null>(null);
  const [achievements, setAchievements] = useState<Achievement[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isEditingGoal, setIsEditingGoal] = useState(false);
  const [goalInput, setGoalInput] = useState("");
  const [goalError, setGoalError] = useState<string | null>(null);

  useEffect(() => {
    fetchMyStats()
      .then(setStats)
      .catch(() => setError("Something went wrong loading your progress."));
    getVocabularySuggestions()
      .then(setSuggestions)
      .catch(() => setSuggestions([])); // non-critical widget, fail quietly
    getMyAchievements()
      .then(setAchievements)
      .catch(() => setAchievements([]));
  }, []);

  async function handleSaveGoal() {
    const parsed = Number(goalInput);
    // Mirrors the backend's DailyGoalUpdate bounds (1–200). The input's
    // min/max attributes don't help here: this button isn't a form
    // submit, so native validation never runs, and previously a typed
    // out-of-range value failed silently (backend 422, empty catch).
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > 200) {
      setGoalError("The goal must be a whole number between 1 and 200.");
      return;
    }
    setGoalError(null);
    try {
      await updateDailyGoal(parsed);
      setStats((prev) => (prev ? { ...prev, daily_goal: parsed } : prev));
      setIsEditingGoal(false);
      toast.success("Daily goal updated");
    } catch {
      // leave the form open so the person can retry
      setGoalError("Couldn't save your goal. Please try again.");
    }
  }

  return (
    <div className={styles.page}>
      <h1>Your progress</h1>
      <p className={styles.subtitle}>Keep your streak alive, finish your courses.</p>

      {error && <ErrorState message={error} />}
      {!error && !stats && <LoadingState label="Loading progress" />}

      {stats && (
        <>
          <div className={styles.streakCard}>
            <svg
              className={styles.flameIcon}
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 2c1 3-2 4-2 7a4 4 0 0 0 8 0c0-1-.5-2-1-2 .5 2-1 3-2 3-1.5 0-2-1.5-1-3-2 0-4 2-4 5a5 5 0 0 0 10 0c0-5-3-6-3-10-1 1-2 2-2 2s-1-1-3-2Z" />
            </svg>
            <div>
              <span className={styles.streakNumber}>{stats.current_streak}</span>
              <span className={styles.streakLabel}>day streak</span>
            </div>
            {stats.longest_streak > stats.current_streak && (
              <span className={styles.streakBest}>Best: {stats.longest_streak} days</span>
            )}
          </div>

          <div className={styles.goalCard}>
            <div className={styles.goalHead}>
              <span className={styles.goalTitle}>Today's goal</span>
              {!isEditingGoal && (
                <button
                  type="button"
                  className={styles.goalEditButton}
                  onClick={() => {
                    setGoalInput(String(stats.daily_goal));
                    setGoalError(null);
                    setIsEditingGoal(true);
                  }}
                >
                  Edit
                </button>
              )}
            </div>
            {isEditingGoal ? (
              <>
                <div className={styles.goalEditRow}>
                  <input
                    type="number"
                    aria-label="Daily review goal"
                    min={1}
                    max={200}
                    className={styles.goalInput}
                    value={goalInput}
                    onChange={(e) => setGoalInput(e.target.value)}
                    autoFocus
                  />
                  <button type="button" className={styles.goalSaveButton} onClick={handleSaveGoal}>
                    Save
                  </button>
                </div>
                {goalError && <p className={styles.goalError}>{goalError}</p>}
              </>
            ) : (
              <>
                <p className={styles.goalDetail}>
                  {stats.reviews_today} / {stats.daily_goal} words reviewed today
                </p>
                <div className={styles.progressTrack}>
                  <div
                    className={styles.progressFill}
                    style={{
                      width: `${Math.min(100, (stats.reviews_today / stats.daily_goal) * 100)}%`,
                    }}
                  />
                </div>
              </>
            )}
          </div>

          <div className={styles.statGrid}>
            <div className={styles.statCard}>
              <span className={styles.statNumber}>{stats.total_translations}</span>
              <span className={styles.statLabel}>translations made</span>
            </div>
            <div className={styles.statCard}>
              <span className={styles.statNumber}>{stats.total_quiz_attempts}</span>
              <span className={styles.statLabel}>quizzes taken</span>
            </div>
            <div className={styles.statCard}>
              <span className={styles.statNumber}>{stats.average_quiz_score}%</span>
              <span className={styles.statLabel}>average score</span>
            </div>
          </div>

          {achievements && achievements.length > 0 && (
            <>
              <h2 className={styles.sectionTitle}>Badges earned</h2>
              <div className={styles.badgeGrid}>
                {achievements.map((a) => (
                  <div key={a.code} className={styles.badgeCard} title={a.description}>
                    <span className={styles.badgeIcon} aria-hidden="true">
                      🏅
                    </span>
                    <span className={styles.badgeName}>{a.name}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {suggestions && suggestions.length > 0 && (
            <>
              <h2 className={styles.sectionTitle}>Picked up from your translations</h2>
              <p className={styles.suggestionIntro}>
                You've translated these words more than once — worth adding to your
                vocabulary practice?
              </p>
              <div className={styles.suggestionList}>
                {suggestions.map((s) => (
                  <Link
                    key={s.vocabulary_item_id}
                    to={`/lessons/${s.lesson_id}`}
                    className={styles.suggestionCard}
                  >
                    <div>
                      <span className={styles.suggestionWord}>{s.word}</span>
                      <span className={styles.suggestionTranslation}>{s.translation}</span>
                    </div>
                    <span className={styles.suggestionFrequency}>
                      seen {s.frequency}×
                    </span>
                  </Link>
                ))}
              </div>
            </>
          )}

          <h2 className={styles.sectionTitle}>Courses</h2>
          <div className={styles.courseList}>
            {stats.courses.map((course) => (
              <Link
                key={course.course_id}
                to={`/courses/${course.course_id}`}
                className={styles.courseCard}
              >
                <div className={styles.courseHead}>
                  <span className={styles.courseTitle}>{course.course_title}</span>
                  <span className={styles.coursePercentage}>
                    {course.completion_percentage}%
                  </span>
                </div>
                <div className={styles.progressTrack}>
                  <div
                    className={styles.progressFill}
                    style={{ width: `${course.completion_percentage}%` }}
                  />
                </div>
                <span className={styles.courseDetail}>
                  {course.completed_lessons} / {course.total_lessons} lessons completed
                </span>
              </Link>
            ))}
            {stats.courses.length === 0 && (
              <p className={styles.empty}>No courses yet.</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
