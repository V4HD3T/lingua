import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { CoursesPage } from "./CoursesPage";
import { renderPage } from "../test/harness";
import * as coursesApi from "../api/courses";
import type { Course, Page } from "../types";

/**
 * The catalogue arrives inside the v0.0.8 pagination envelope, so the page
 * has to unwrap `items` -- rendering the envelope itself would show
 * nothing at all -- and it has to tell "no courses yet" apart from "the
 * request failed", which look identical if only the happy path is checked.
 */

function course(overrides: Partial<Course> = {}): Course {
  return {
    id: 1,
    language_code: "es",
    title: "Spanish for beginners",
    level: "A1",
    description: "Start from hello.",
    ...overrides,
  };
}

function envelope(items: Course[]): Page<Course> {
  return { items, total: items.length, limit: 100, offset: 0 };
}

describe("CoursesPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("lists the catalogue out of the pagination envelope", async () => {
    vi.spyOn(coursesApi, "listCourses").mockResolvedValue(
      envelope([course(), course({ id: 2, title: "Türkçe A1", level: "A1" })])
    );

    renderPage(<CoursesPage />);

    expect(await screen.findByRole("link", { name: /Spanish for beginners/ })).toHaveAttribute(
      "href",
      "/courses/1"
    );
    expect(screen.getByRole("link", { name: /Türkçe A1/ })).toHaveAttribute("href", "/courses/2");
  });

  it("says the catalogue is empty when it really is", async () => {
    vi.spyOn(coursesApi, "listCourses").mockResolvedValue(envelope([]));

    renderPage(<CoursesPage />);

    await screen.findByText("No courses yet.");
  });

  it("reports a failed load instead of an empty catalogue", async () => {
    vi.spyOn(coursesApi, "listCourses").mockRejectedValue(new Error("network"));

    renderPage(<CoursesPage />);

    await screen.findByText("Something went wrong loading the courses.");
    expect(screen.queryByText("No courses yet.")).not.toBeInTheDocument();
  });
});
