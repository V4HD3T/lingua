import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchMyStats } from "../api/stats";
import { getVocabularySuggestions } from "../api/suggestions";
import { LoadingState, ErrorState } from "../components/StatusMessage";
import type { UserStats, VocabularySuggestion } from "../types";
import styles from "./ProgressPage.module.css";

export function ProgressPage() {
  const [stats, setStats] = useState<UserStats | null>(null);
  const [suggestions, setSuggestions] = useState<VocabularySuggestion[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMyStats()
      .then(setStats)
      .catch(() => setError("Something went wrong loading your progress."));
    getVocabularySuggestions()
      .then(setSuggestions)
      .catch(() => setSuggestions([])); // non-critical widget, fail quietly
  }, []);

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
