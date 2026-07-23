import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { CourseDetailPage } from "./CourseDetailPage";
import { renderPage } from "../test/harness";
import * as coursesApi from "../api/courses";
import type { Course, Lesson } from "../types";

/**
 * The course and its lessons are fetched together (Promise.all), so a
 * failure in either one has to be reported -- a half-rendered course with
 * a silently empty lesson list is the failure mode worth guarding.
 */

const COURSE: Course = {
  id: 5,
  language_code: "es",
  title: "Spanish for beginners",
  level: "A1",
  description: "Start from hello.",
};

function lesson(id: number, order: number, title: string): Lesson {
  return {
    id,
    course_id: 5,
    title,
    content: "…",
    order,
    language_code: "es",
    grammar_note: "",
    cultural_note: "",
  };
}

function renderCourse() {
  return renderPage(<CourseDetailPage />, {
    path: "/courses/:courseId",
    entry: "/courses/5",
  });
}

describe("CourseDetailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the course with its lessons in order", async () => {
    vi.spyOn(coursesApi, "getCourse").mockResolvedValue(COURSE);
    vi.spyOn(coursesApi, "listLessons").mockResolvedValue([
      lesson(11, 1, "Greetings"),
      lesson(12, 2, "Numbers"),
    ]);

    renderCourse();

    await screen.findByRole("heading", { name: "Spanish for beginners" });
    expect(screen.getByRole("link", { name: /Greetings/ })).toHaveAttribute("href", "/lessons/11");
    expect(screen.getByRole("link", { name: /Numbers/ })).toHaveAttribute("href", "/lessons/12");
  });

  it("reports the failure when the lessons don't arrive, rather than an empty course", async () => {
    vi.spyOn(coursesApi, "getCourse").mockResolvedValue(COURSE);
    vi.spyOn(coursesApi, "listLessons").mockRejectedValue(new Error("network"));

    renderCourse();

    await screen.findByText("Something went wrong loading this course.");
    expect(screen.queryByRole("heading", { name: "Spanish for beginners" })).not.toBeInTheDocument();
  });
});
