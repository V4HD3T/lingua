import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProgressPage } from "./ProgressPage";
import { renderPage, signIn } from "../test/harness";
import * as statsApi from "../api/stats";
import * as suggestionsApi from "../api/suggestions";
import * as achievementsApi from "../api/achievements";
import * as authApi from "../api/auth";
import type { UserStats } from "../types";

/**
 * Two things on this page have already gone wrong once and are worth
 * pinning down. The daily-goal editor isn't inside a form, so the input's
 * min/max never fire and an out-of-range value used to die as a silent
 * backend 422 (v0.1.7). And the verification notice (v0.1.12) has to
 * appear only for the people it applies to -- it is information, not an
 * obstacle, and showing it to a verified learner would read as one.
 */

function statsFixture(overrides: Partial<UserStats> = {}): UserStats {
  return {
    current_streak: 3,
    longest_streak: 9,
    total_translations: 42,
    total_quiz_attempts: 5,
    average_quiz_score: 80,
    courses: [],
    daily_goal: 10,
    reviews_today: 4,
    ...overrides,
  };
}

describe("ProgressPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    signIn();
    vi.spyOn(suggestionsApi, "getVocabularySuggestions").mockResolvedValue([]);
    vi.spyOn(achievementsApi, "getMyAchievements").mockResolvedValue([]);
  });

  it("shows the streak and today's standing against the goal", async () => {
    vi.spyOn(statsApi, "fetchMyStats").mockResolvedValue(statsFixture());

    renderPage(<ProgressPage />);

    expect(await screen.findByText("3")).toBeInTheDocument();
    expect(screen.getByText("Best: 9 days")).toBeInTheDocument();
    expect(screen.getByText("4 / 10 words reviewed today")).toBeInTheDocument();
  });

  it("rejects an out-of-range goal in the page instead of letting the API 422 it", async () => {
    vi.spyOn(statsApi, "fetchMyStats").mockResolvedValue(statsFixture());
    const update = vi.spyOn(authApi, "updateDailyGoal");

    renderPage(<ProgressPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    const input = screen.getByLabelText("Daily review goal");
    await userEvent.clear(input);
    await userEvent.type(input, "500");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByText("The goal must be a whole number between 1 and 200.");
    expect(update).not.toHaveBeenCalled();
    // The editor stays open: the value is still there to correct.
    expect(screen.getByLabelText("Daily review goal")).toHaveValue(500);
  });

  it("saves a goal in range and shows the new one straight away", async () => {
    vi.spyOn(statsApi, "fetchMyStats").mockResolvedValue(statsFixture());
    const update = vi
      .spyOn(authApi, "updateDailyGoal")
      .mockResolvedValue({ ...signIn(), daily_review_goal: 25 });

    renderPage(<ProgressPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    const input = screen.getByLabelText("Daily review goal");
    await userEvent.clear(input);
    await userEvent.type(input, "25");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(update).toHaveBeenCalledWith(25);
    // No refetch: the page updates what it already has.
    await screen.findByText("4 / 25 words reviewed today");
    expect(await screen.findByText("Daily goal updated")).toBeInTheDocument();
  });

  it("keeps the editor open when saving the goal fails", async () => {
    vi.spyOn(statsApi, "fetchMyStats").mockResolvedValue(statsFixture());
    vi.spyOn(authApi, "updateDailyGoal").mockRejectedValue(new Error("network"));

    renderPage(<ProgressPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByText("Couldn't save your goal. Please try again.");
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("tells an unverified learner where they stand and offers a fresh link", async () => {
    signIn({ is_verified: false });
    vi.spyOn(statsApi, "fetchMyStats").mockResolvedValue(statsFixture());
    const resend = vi
      .spyOn(authApi, "resendVerification")
      .mockResolvedValue({ message: "Verification email sent" });

    renderPage(<ProgressPage />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Resend verification email" })
    );

    expect(resend).toHaveBeenCalled();
    expect(await screen.findByText("Verification email sent")).toBeInTheDocument();
  });

  it("says nothing about verification to someone who has already done it", async () => {
    vi.spyOn(statsApi, "fetchMyStats").mockResolvedValue(statsFixture());

    renderPage(<ProgressPage />);

    await screen.findByText("4 / 10 words reviewed today");
    expect(
      screen.queryByRole("button", { name: "Resend verification email" })
    ).not.toBeInTheDocument();
  });

  it("reports a progress page that couldn't load", async () => {
    vi.spyOn(statsApi, "fetchMyStats").mockRejectedValue(new Error("network"));

    renderPage(<ProgressPage />);

    await screen.findByText("Something went wrong loading your progress.");
  });
});
