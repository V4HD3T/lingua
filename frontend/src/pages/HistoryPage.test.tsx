import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HistoryPage } from "./HistoryPage";
import { renderPage, signIn } from "../test/harness";
import * as translateApi from "../api/translate";
import type { Page, TranslateResult } from "../types";

/**
 * Paging is the whole of this page's logic: the second request has to be
 * offset by what is already on screen, and the button has to disappear
 * once the list has caught up with the total. Getting the offset wrong
 * doesn't crash anything -- it just quietly serves the first page twice.
 */

function entry(index: number): TranslateResult {
  return {
    source_text: `source ${index}`,
    translated_text: `translation ${index}`,
    source_lang: "en",
    target_lang: "es",
    confidence: 0.9,
    alternatives: [],
    idiom_warnings: [],
    new_achievements: [],
  };
}

function page(items: TranslateResult[], total: number, offset = 0): Page<TranslateResult> {
  return { items, total, limit: 20, offset };
}

describe("HistoryPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    signIn();
  });

  it("asks for the next page from where the list ends, and appends it", async () => {
    const first = Array.from({ length: 20 }, (_, i) => entry(i));
    const fetchHistory = vi
      .spyOn(translateApi, "fetchTranslationHistory")
      .mockResolvedValueOnce(page(first, 21))
      .mockResolvedValueOnce(page([entry(20)], 21, 20));

    renderPage(<HistoryPage />);

    await screen.findByText("translation 0");
    expect(fetchHistory).toHaveBeenCalledWith(20, 0);
    expect(screen.getByText("Showing 20 of 21")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Load more" }));

    expect(fetchHistory).toHaveBeenLastCalledWith(20, 20);
    await screen.findByText("translation 20");
    // Appended, not replaced.
    expect(screen.getByText("translation 0")).toBeInTheDocument();
    // Nothing left to fetch, so the button goes away.
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("doesn't offer more when the first page is all there is", async () => {
    vi.spyOn(translateApi, "fetchTranslationHistory").mockResolvedValue(
      page([entry(0)], 1)
    );

    renderPage(<HistoryPage />);

    await screen.findByText("translation 0");
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("keeps what's loaded and explains the failure when the next page doesn't arrive", async () => {
    vi.spyOn(translateApi, "fetchTranslationHistory")
      .mockResolvedValueOnce(page([entry(0)], 5))
      .mockRejectedValueOnce(new Error("network"));

    renderPage(<HistoryPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Load more" }));

    await screen.findByText("Something went wrong loading more history.");
    expect(screen.getByText("translation 0")).toBeInTheDocument();
  });

  it("says the history is empty rather than showing an empty list", async () => {
    vi.spyOn(translateApi, "fetchTranslationHistory").mockResolvedValue(page([], 0));

    renderPage(<HistoryPage />);

    await screen.findByText("You haven't translated anything yet.");
  });
});
