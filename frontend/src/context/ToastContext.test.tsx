import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { ToastProvider, useToast } from "./ToastContext";

function Trigger() {
  const toast = useToast();
  return (
    <>
      <button onClick={() => toast.success("Saved!")}>ok</button>
      <button onClick={() => toast.error("Broke!")}>bad</button>
    </>
  );
}

function renderWithProvider() {
  return render(
    <ToastProvider>
      <Trigger />
    </ToastProvider>
  );
}

// fireEvent (not userEvent) on purpose: these are plain button clicks, and
// userEvent's internal delays deadlock against vi.useFakeTimers unless the
// clock is wired through -- machinery this file doesn't need.
describe("ToastContext", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a success toast when triggered", () => {
    renderWithProvider();
    fireEvent.click(screen.getByText("ok"));
    expect(screen.getByText("Saved!")).toBeInTheDocument();
  });

  it("marks error toasts as alerts for assertive announcement", () => {
    renderWithProvider();
    fireEvent.click(screen.getByText("bad"));
    expect(screen.getByRole("alert")).toHaveTextContent("Broke!");
  });

  it("auto-dismisses success after 4s while errors linger to 7s", () => {
    renderWithProvider();
    fireEvent.click(screen.getByText("ok"));
    fireEvent.click(screen.getByText("bad"));

    act(() => vi.advanceTimersByTime(4000));
    expect(screen.queryByText("Saved!")).not.toBeInTheDocument();
    expect(screen.getByText("Broke!")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(3000));
    expect(screen.queryByText("Broke!")).not.toBeInTheDocument();
  });

  it("dismisses on demand via the close button", () => {
    renderWithProvider();
    fireEvent.click(screen.getByText("ok"));
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));
    expect(screen.queryByText("Saved!")).not.toBeInTheDocument();
  });

  it("refuses to work outside its provider", () => {
    const silence = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Trigger />)).toThrow("useToast must be used inside a ToastProvider");
    silence.mockRestore();
  });
});
