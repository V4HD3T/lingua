import { apiRequest } from "./client";
import type { Quiz, QuizResult } from "../types";

export function getQuizByLesson(lessonId: number): Promise<Quiz> {
  // auth matters here twice over: adaptive difficulty only activates for
  // a known learner, and (v0.0.9) the backend records which questions it
  // served as a QuizSession -- submissions are graded against that served
  // set, and only authenticated fetches create one.
  //
  // Because of that second effect, this call is for *playing* a quiz.
  // Anything that only needs to know whether a quiz exists must use
  // lessonHasQuiz below, or merely browsing lessons would mint a
  // throwaway session row per page view.
  return apiRequest<Quiz>(`/lessons/${lessonId}/quiz`, { auth: true });
}

export function lessonHasQuiz(lessonId: number): Promise<boolean> {
  // Deliberately unauthenticated: the backend only records a QuizSession
  // for authenticated fetches, so an anonymous request answers "does a
  // quiz exist?" without creating state. Existence doesn't depend on who
  // is asking.
  return apiRequest<Quiz>(`/lessons/${lessonId}/quiz`)
    .then(() => true)
    .catch(() => false);
}

export function submitQuiz(
  quizId: number,
  sessionId: number,
  answers: Record<string, string>
): Promise<QuizResult> {
  return apiRequest<QuizResult>(`/quizzes/${quizId}/submit`, {
    method: "POST",
    body: { session_id: sessionId, answers },
    auth: true,
  });
}
