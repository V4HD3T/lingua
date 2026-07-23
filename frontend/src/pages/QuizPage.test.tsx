import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuizPage } from "./QuizPage";
import { renderPage, signIn } from "../test/harness";
import * as quizApi from "../api/quizzes";
import type { Quiz } from "../types";

/**
 * Grading happens server-side against the served set (the v0.0.9
 * QuizSession), so the page's real responsibility is what it sends: every
 * answer, keyed by question id, together with the session the questions
 * came from. The two guards in front of that -- unanswered questions, and
 * a missing session -- exist to fail on this side of the network rather
 * than as a 400 the learner can't act on.
 */

function quizFixture(overrides: Partial<Quiz> = {}): Quiz {
  return {
    id: 3,
    title: "Greetings",
    quiz_type: "mixed",
    language_code: "es",
    session_id: 42,
    questions: [
      {
        id: 11,
        question_type: "multiple_choice",
        question_text: "What does 'hola' mean?",
        options: ["hello", "goodbye"],
      },
      {
        id: 12,
        question_type: "fill_blank",
        question_text: "Buenas ___",
        options: [],
      },
    ],
    ...overrides,
  };
}

function renderQuiz() {
  return renderPage(<QuizPage />, {
    path: "/lessons/:lessonId/quiz",
    entry: "/lessons/7/quiz",
  });
}

describe("QuizPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("submits every answer with the session the questions were served from", async () => {
    signIn();
    vi.spyOn(quizApi, "getQuizByLesson").mockResolvedValue(quizFixture());
    const submit = vi.spyOn(quizApi, "submitQuiz").mockResolvedValue({
      score: 100,
      total_questions: 2,
      correct_count: 2,
      new_achievements: [],
    });

    renderQuiz();

    await userEvent.click(await screen.findByRole("radio", { name: "hello" }));
    await userEvent.type(screen.getByPlaceholderText("Type your answer..."), "tardes");
    await userEvent.click(screen.getByRole("button", { name: "Submit answers" }));

    expect(submit).toHaveBeenCalledWith(3, 42, { "11": "hello", "12": "tardes" });
    await screen.findByText("100%");
    expect(screen.getByText(/You got 2 out of 2 questions right\./)).toBeInTheDocument();
  });

  it("refuses to submit a half-finished quiz", async () => {
    signIn();
    vi.spyOn(quizApi, "getQuizByLesson").mockResolvedValue(quizFixture());
    const submit = vi.spyOn(quizApi, "submitQuiz");

    renderQuiz();

    await userEvent.click(await screen.findByRole("radio", { name: "hello" }));
    await userEvent.click(screen.getByRole("button", { name: "Submit answers" }));

    // `required` stops this one in the browser before the page's own check
    // ever runs, so what matters here is the outcome: nothing goes out.
    expect(submit).not.toHaveBeenCalled();
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
  });

  it("counts a whitespace-only answer as unanswered, which the browser's own check won't", async () => {
    signIn();
    vi.spyOn(quizApi, "getQuizByLesson").mockResolvedValue(quizFixture());
    const submit = vi.spyOn(quizApi, "submitQuiz");

    renderQuiz();

    await userEvent.click(await screen.findByRole("radio", { name: "hello" }));
    await userEvent.type(screen.getByPlaceholderText("Type your answer..."), "   ");
    await userEvent.click(screen.getByRole("button", { name: "Submit answers" }));

    await screen.findByText("Please answer every question before submitting.");
    expect(submit).not.toHaveBeenCalled();
  });

  it("stops a submission that has no served-set session rather than letting the API reject it", async () => {
    signIn();
    vi.spyOn(quizApi, "getQuizByLesson").mockResolvedValue(quizFixture({ session_id: null }));
    const submit = vi.spyOn(quizApi, "submitQuiz");

    renderQuiz();

    await userEvent.click(await screen.findByRole("radio", { name: "hello" }));
    await userEvent.type(screen.getByPlaceholderText("Type your answer..."), "tardes");
    await userEvent.click(screen.getByRole("button", { name: "Submit answers" }));

    await screen.findByText("Your quiz session is missing — please reload the page.");
    expect(submit).not.toHaveBeenCalled();
  });

  it("clears the previous attempt when the learner tries again", async () => {
    signIn();
    vi.spyOn(quizApi, "getQuizByLesson").mockResolvedValue(quizFixture());
    vi.spyOn(quizApi, "submitQuiz").mockResolvedValue({
      score: 50,
      total_questions: 2,
      correct_count: 1,
      new_achievements: [],
    });

    renderQuiz();

    await userEvent.click(await screen.findByRole("radio", { name: "goodbye" }));
    await userEvent.type(screen.getByPlaceholderText("Type your answer..."), "noches");
    await userEvent.click(screen.getByRole("button", { name: "Submit answers" }));

    await screen.findByText("50%");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    // A second attempt starts empty -- keeping the old answers would let
    // someone re-submit the same wrong ones by reflex.
    expect(await screen.findByRole("radio", { name: "goodbye" })).not.toBeChecked();
    expect(screen.getByPlaceholderText("Type your answer...")).toHaveValue("");
  });

  it("shows an anonymous visitor the way in rather than a quiz", async () => {
    vi.spyOn(quizApi, "getQuizByLesson").mockResolvedValue(quizFixture({ session_id: null }));

    renderQuiz();

    await screen.findByText("You need to log in to take this quiz.");
    expect(screen.getByRole("link", { name: "Log in →" })).toHaveAttribute("href", "/login");
    expect(screen.queryByRole("button", { name: "Submit answers" })).not.toBeInTheDocument();
  });
});
