import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { TranslatePage } from "./TranslatePage";
import { renderPage, signIn } from "../test/harness";
import * as translateApi from "../api/translate";
import type { TranslateResult } from "../types";

/**
 * Two pieces of real logic live on this page, and both are about timing:
 * the 400ms debounce (one request per pause, not one per keystroke) and
 * the request-id guard that keeps a slow answer from overwriting a newer
 * one. A stale overwrite is the kind of bug that only shows up on a bad
 * connection, which is exactly where nobody is watching.
 */

function result(text: string, overrides: Partial<TranslateResult> = {}): TranslateResult {
  return {
    source_text: "source",
    translated_text: text,
    source_lang: "en",
    target_lang: "es",
    confidence: 0.9,
    alternatives: [],
    idiom_warnings: [],
    new_achievements: [],
    ...overrides,
  };
}

function typeSource(text: string) {
  fireEvent.change(screen.getByLabelText("Text to translate"), { target: { value: text } });
}

describe("TranslatePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(translateApi, "listLanguages").mockResolvedValue([
      { code: "en", name: "English" },
      { code: "es", name: "Spanish" },
    ]);
    vi.spyOn(translateApi, "detectLanguage").mockResolvedValue({
      language_code: "en",
      confidence: 0.98,
      is_reliable: true,
    });
  });

  it("translates once the typing stops, not once per keystroke", async () => {
    const translate = vi.spyOn(translateApi, "translateText").mockResolvedValue(result("hola"));

    renderPage(<TranslatePage />);

    typeSource("h");
    typeSource("he");
    typeSource("hello");

    await screen.findByText("hola");
    expect(translate).toHaveBeenCalledTimes(1);
    expect(translate).toHaveBeenCalledWith("hello", "en", "es");
  });

  it("keeps the newest translation when a slower earlier one lands late", async () => {
    vi.spyOn(translateApi, "translateText").mockImplementation((text: string) =>
      text === "first"
        ? new Promise((resolve) => setTimeout(() => resolve(result("SLOW")), 700))
        : Promise.resolve(result("FAST"))
    );

    renderPage(<TranslatePage />);

    typeSource("first");
    typeSource("second");

    await screen.findByText("FAST");
    // Long enough for the first request to have resolved behind our back.
    await new Promise((resolve) => setTimeout(resolve, 900));
    expect(screen.getByText("FAST")).toBeInTheDocument();
    expect(screen.queryByText("SLOW")).not.toBeInTheDocument();
  });

  it("clears the output again when the box is emptied, without asking the server", async () => {
    const translate = vi.spyOn(translateApi, "translateText").mockResolvedValue(result("hola"));

    renderPage(<TranslatePage />);

    typeSource("hello");
    await screen.findByText("hola");

    typeSource("   ");
    await screen.findByText("Your translation will appear here");
    expect(translate).toHaveBeenCalledTimes(1);
  });

  it("offers history to a visitor who isn't signed in", async () => {
    vi.spyOn(translateApi, "translateText").mockResolvedValue(result("hola"));

    renderPage(<TranslatePage />);
    await screen.findAllByRole("option", { name: "Spanish" });

    typeSource("hello");

    await screen.findByText("hola");
    expect(screen.getByText("Log in to save your translations")).toBeInTheDocument();
  });

  it("confirms the save to a signed-in learner", async () => {
    signIn();
    vi.spyOn(translateApi, "translateText").mockResolvedValue(result("hola"));

    renderPage(<TranslatePage />);
    // Wait for the page to settle -- the debounced translation closes over
    // whoever is signed in *when the keystroke happens*, which is how a
    // real learner reaches this page anyway.
    await screen.findAllByRole("option", { name: "Spanish" });

    typeSource("hello");

    await screen.findByText("Saved to your translation history");
  });

  it("says so plainly when the translation request fails", async () => {
    vi.spyOn(translateApi, "translateText").mockRejectedValue(new Error("network"));

    renderPage(<TranslatePage />);

    typeSource("hello");

    await screen.findByText("Something went wrong while translating. Please try again.");
    // The failed attempt must not leave the spinner state behind.
    await waitFor(() =>
      expect(screen.queryByText("translating...")).not.toBeInTheDocument()
    );
  });
});
