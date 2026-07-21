import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider } from "../context/ToastContext";
import { CopyButton } from "./CopyButton";

function renderCopy(text = "hola mundo") {
  return render(
    <ToastProvider>
      <CopyButton text={text} label="Copy translation" />
    </ToastProvider>
  );
}

describe("CopyButton", () => {
  const writeText = vi.fn();

  beforeEach(() => {
    writeText.mockReset();
    // jsdom ships no clipboard at all
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
  });

  it("copies the text and confirms via toast", async () => {
    writeText.mockResolvedValue(undefined);
    renderCopy();
    await userEvent.click(screen.getByRole("button", { name: "Copy translation" }));
    expect(writeText).toHaveBeenCalledWith("hola mundo");
    expect(await screen.findByText("Copied to clipboard")).toBeInTheDocument();
  });

  it("reports blocked clipboard access instead of failing silently", async () => {
    writeText.mockRejectedValue(new Error("denied"));
    renderCopy();
    await userEvent.click(screen.getByRole("button", { name: "Copy translation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't copy");
  });
});
