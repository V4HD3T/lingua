import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { LessonDetailPage } from "./LessonDetailPage";
import { renderPage } from "../test/harness";
import * as coursesApi from "../api/courses";
import * as quizApi from "../api/quizzes";
import type { Lesson, VocabularyItem } from "../types";

/**
 * The quiz button is the thing to hold still here. Whether it appears is
 * asked through `lessonHasQuiz`, which is deliberately the unauthenticated
 * existence check -- the authenticated fetch records a QuizSession, and
 * merely opening a lesson must not mint one. Pointing this page at
 * getQuizByLesson would leave a throwaway session row per page view.
 */

function lessonFixture(overrides: Partial<Lesson> = {}): Lesson {
  return {
    id: 11,
    course_id: 5,
    title: "Greetings",
    content: "Hello and goodbye.",
    order: 1,
    language_code: "es",
    grammar_note: "",
    cultural_note: "",
    ...overrides,
  };
}

const VOCABULARY: VocabularyItem[] = [
  { id: 101, word: "hola", translation: "hello", example_sentence: "¡Hola!" },
];

function renderLesson() {
  return renderPage(<LessonDetailPage />, {
    path: "/lessons/:lessonId",
    entry: "/lessons/11",
  });
}

describe("LessonDetailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(coursesApi, "listVocabulary").mockResolvedValue(VOCABULARY);
  });

  it("asks about the quiz without opening one, and links to it when there is one", async () => {
    vi.spyOn(coursesApi, "getLesson").mockResolvedValue(lessonFixture());
    const existence = vi.spyOn(quizApi, "lessonHasQuiz").mockResolvedValue(true);
    const play = vi.spyOn(quizApi, "getQuizByLesson");

    renderLesson();

    expect(await screen.findByRole("link", { name: "Start quiz" })).toHaveAttribute(
      "href",
      "/lessons/11/quiz"
    );
    expect(existence).toHaveBeenCalledWith(11);
    expect(play).not.toHaveBeenCalled();
  });

  it("offers no quiz button for a lesson that hasn't got one", async () => {
    vi.spyOn(coursesApi, "getLesson").mockResolvedValue(lessonFixture());
    vi.spyOn(quizApi, "lessonHasQuiz").mockResolvedValue(false);

    renderLesson();

    await screen.findByText("hola");
    expect(screen.queryByRole("link", { name: "Start quiz" })).not.toBeInTheDocument();
  });

  it("shows the notes a lesson actually has, and no empty cards for the rest", async () => {
    vi.spyOn(coursesApi, "getLesson").mockResolvedValue(
      lessonFixture({ grammar_note: "Nouns carry gender in Spanish." })
    );
    vi.spyOn(quizApi, "lessonHasQuiz").mockResolvedValue(false);

    renderLesson();

    expect(await screen.findByText("Grammar note")).toBeInTheDocument();
    expect(screen.getByText("Nouns carry gender in Spanish.")).toBeInTheDocument();
    expect(screen.queryByText("Cultural note")).not.toBeInTheDocument();
  });

  it("reports a lesson that couldn't be loaded", async () => {
    vi.spyOn(coursesApi, "getLesson").mockRejectedValue(new Error("network"));
    vi.spyOn(quizApi, "lessonHasQuiz").mockResolvedValue(false);

    renderLesson();

    await screen.findByText("Something went wrong loading this lesson.");
  });
});
