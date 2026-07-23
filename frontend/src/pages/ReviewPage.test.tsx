import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReviewPage } from "./ReviewPage";
import { renderPage, signIn } from "../test/harness";
import * as reviewApi from "../api/review";
import type { ReviewQueueItem } from "../types";

/**
 * A review session is a small state machine -- hidden answer, revealed
 * answer, rated, next card -- and the ratings it sends are SM-2 quality
 * values, not button labels. Send the wrong number and the scheduler
 * quietly learns the wrong thing about how well the word is known, which
 * no error message will ever tell anyone about.
 */

function item(overrides: Partial<ReviewQueueItem> = {}): ReviewQueueItem {
  return {
    vocabulary_item_id: 1,
    word: "hola",
    translation: "hello",
    example_sentence: "¡Hola, amigo!",
    lesson_id: 4,
    language_code: "es",
    is_new: false,
    ...overrides,
  };
}

function reviewResult() {
  return {
    vocabulary_item_id: 1,
    repetitions: 1,
    ease_factor: 2.5,
    interval_days: 1,
    next_review_date: "2026-07-24",
    new_achievements: [],
  };
}

describe("ReviewPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    signIn();
  });

  it("keeps the answer hidden until the learner asks for it", async () => {
    vi.spyOn(reviewApi, "getReviewQueue").mockResolvedValue([item()]);

    renderPage(<ReviewPage />);

    await screen.findByText("hola");
    expect(screen.queryByText("hello")).not.toBeInTheDocument();
    // Rating before recalling would defeat the whole exercise.
    expect(screen.queryByRole("button", { name: "Good" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Show answer" }));

    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("¡Hola, amigo!")).toBeInTheDocument();
  });

  it("sends SM-2 quality values, not the labels on the buttons", async () => {
    vi.spyOn(reviewApi, "getReviewQueue").mockResolvedValue([item()]);
    const submit = vi.spyOn(reviewApi, "submitReview").mockResolvedValue(reviewResult());

    renderPage(<ReviewPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Show answer" }));
    await userEvent.click(screen.getByRole("button", { name: "Again" }));

    expect(submit).toHaveBeenCalledWith(1, 1);
  });

  it("moves to the next card with its answer hidden again, then reports the session", async () => {
    vi.spyOn(reviewApi, "getReviewQueue").mockResolvedValue([
      item(),
      item({ vocabulary_item_id: 2, word: "gato", translation: "cat", is_new: true }),
    ]);
    const submit = vi.spyOn(reviewApi, "submitReview").mockResolvedValue(reviewResult());

    renderPage(<ReviewPage />);

    expect(await screen.findByText("1 / 2")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show answer" }));
    await userEvent.click(screen.getByRole("button", { name: "Good" }));

    await screen.findByText("gato");
    expect(screen.getByText("2 / 2")).toBeInTheDocument();
    expect(screen.getByText("new")).toBeInTheDocument();
    // The revealed state belongs to the card, not to the session.
    expect(screen.queryByText("cat")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Show answer" }));
    await userEvent.click(screen.getByRole("button", { name: "Easy" }));

    await screen.findByText("All caught up ✓");
    expect(screen.getByText("You reviewed 2 words.")).toBeInTheDocument();
    expect(submit).toHaveBeenNthCalledWith(2, 2, 5);
  });

  it("holds the card in place when saving the rating fails", async () => {
    vi.spyOn(reviewApi, "getReviewQueue").mockResolvedValue([item(), item({ vocabulary_item_id: 2, word: "gato" })]);
    vi.spyOn(reviewApi, "submitReview").mockRejectedValue(new Error("network"));

    renderPage(<ReviewPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Show answer" }));
    await userEvent.click(screen.getByRole("button", { name: "Good" }));

    await screen.findByText("Something went wrong saving your answer.");
    // Advancing past a rating the server never recorded would lose it.
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
    expect(screen.getByText("hola")).toBeInTheDocument();
  });

  it("points at the courses when nothing is due", async () => {
    vi.spyOn(reviewApi, "getReviewQueue").mockResolvedValue([]);

    renderPage(<ReviewPage />);

    await screen.findByText("No words due for review right now.");
    expect(screen.getByRole("link", { name: /Browse courses/ })).toHaveAttribute(
      "href",
      "/courses"
    );
  });

  it("reports a queue that couldn't be loaded instead of showing an empty session", async () => {
    vi.spyOn(reviewApi, "getReviewQueue").mockRejectedValue(new Error("network"));

    renderPage(<ReviewPage />);

    await screen.findByText("Something went wrong loading your review queue.");
    expect(screen.queryByText("No words due for review right now.")).not.toBeInTheDocument();
  });
});
