import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { getQuizByLesson, submitQuiz } from "../api/quizzes";
import { useAuth } from "../context/AuthContext";
import { useSpeechSynthesis } from "../hooks/useSpeechSynthesis";
import { LoadingState, ErrorState } from "../components/StatusMessage";
import { SpeakerButton } from "../components/SpeakerButton";
import { SentenceOrderInput } from "../components/SentenceOrderInput";
import { AchievementToast } from "../components/AchievementToast";
import type { Achievement, Quiz, QuizQuestion, QuizResult } from "../types";
import styles from "./QuizPage.module.css";

function QuestionInput({
  question,
  value,
  onChange,
  languageCode,
}: {
  question: QuizQuestion;
  value: string | undefined;
  onChange: (value: string) => void;
  languageCode: string;
}) {
  const voice = useSpeechSynthesis();

  if (question.question_type === "fill_blank") {
    return (
      <input
        type="text"
        className={styles.textInput}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Type your answer..."
        required
      />
    );
  }

  if (question.question_type === "sentence_order") {
    return <SentenceOrderInput words={question.options} onChange={onChange} />;
  }

  // "listening" and "multiple_choice" both render as a set of options;
  // listening questions additionally get a speaker button up top.
  return (
    <>
      {question.question_type === "listening" && voice.isSupported && question.audio_text && (
        <div className={styles.listenRow}>
          <SpeakerButton
            isSpeaking={voice.isSpeaking}
            onClick={() => voice.speak(question.audio_text!, languageCode)}
            title="Play audio"
          />
          <span className={styles.listenHint}>Tap to listen</span>
        </div>
      )}
      <div className={styles.options}>
        {question.options.map((option) => (
          <label key={option} className={styles.option}>
            <input
              type="radio"
              name={`question-${question.id}`}
              value={option}
              checked={value === option}
              onChange={() => onChange(option)}
              required
            />
            {option}
          </label>
        ))}
      </div>
    </>
  );
}

export function QuizPage() {
  const { lessonId } = useParams<{ lessonId: string }>();
  const { user } = useAuth();
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const [newAchievements, setNewAchievements] = useState<Achievement[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!lessonId) return;
    getQuizByLesson(Number(lessonId))
      .then(setQuiz)
      .catch(() => setError("No quiz was found for this lesson."));
  }, [lessonId]);

  function setAnswer(questionId: number, value: string) {
    setAnswers((prev) => ({ ...prev, [String(questionId)]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!quiz) return;

    const unanswered = quiz.questions.some((q) => !answers[String(q.id)]?.trim());
    if (unanswered) {
      setError("Please answer every question before submitting.");
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      const res = await submitQuiz(quiz.id, answers);
      setResult(res);
      setNewAchievements(res.new_achievements);
    } catch {
      setError("Something went wrong submitting your answers.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleRetry() {
    setResult(null);
    setAnswers({});
  }

  if (!user) {
    return (
      <div className={styles.page}>
        <ErrorState message="You need to log in to take this quiz." />
        <Link to="/login" className={styles.backLink}>
          Log in →
        </Link>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <Link to={`/lessons/${lessonId}`} className={styles.backLink}>
        ← Back to lesson
      </Link>

      {error && <ErrorState message={error} />}
      {!error && !quiz && <LoadingState label="Loading quiz" />}

      {quiz && !result && (
        <>
          <h1>{quiz.title}</h1>
          <form onSubmit={handleSubmit}>
            {quiz.questions.map((question, index) => (
              <fieldset key={question.id} className={styles.question}>
                <legend className={styles.questionText}>
                  {index + 1}. {question.question_text}
                </legend>
                <QuestionInput
                  question={question}
                  value={answers[String(question.id)]}
                  onChange={(value) => setAnswer(question.id, value)}
                  languageCode={quiz.language_code}
                />
              </fieldset>
            ))}

            <button type="submit" className={styles.submit} disabled={isSubmitting}>
              {isSubmitting ? "Submitting..." : "Submit answers"}
            </button>
          </form>
        </>
      )}

      {result && (
        <>
          <div className={styles.result}>
            <span className={styles.resultScore}>{result.score}%</span>
            <p className={styles.resultDetail}>
              You got {result.correct_count} out of {result.total_questions} questions
              right.
            </p>
            <div className={styles.resultActions}>
              <button type="button" className={styles.retryButton} onClick={handleRetry}>
                Try again
              </button>
              <Link to={`/lessons/${lessonId}`} className={styles.backToLesson}>
                Back to lesson
              </Link>
            </div>
          </div>
          <AchievementToast achievements={newAchievements} />
        </>
      )}
    </div>
  );
}
