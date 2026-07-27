import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ErrorBoundary } from "./ErrorBoundary";

/**
 * React unmounts the whole tree on an uncaught render error, on purpose:
 * a half-rendered UI is worse than none. Without a boundary that meant
 * one thrown error in one page blanked the entire document — no message,
 * no navigation, nothing to suggest a reload would help (v0.1.21).
 */

function Explodes(): never {
  throw new Error("Cannot read properties of undefined (reading 'map')");
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    // React logs the caught error itself, and the boundary logs the
    // component stack. Both are wanted in production and are pure noise
    // in a test that is deliberately throwing.
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders its children when nothing goes wrong", () => {
    render(
      <ErrorBoundary>
        <p>the actual page</p>
      </ErrorBoundary>
    );
    expect(screen.getByText("the actual page")).toBeInTheDocument();
  });

  it("shows a recoverable message instead of a blank document", () => {
    render(
      <ErrorBoundary>
        <Explodes />
      </ErrorBoundary>
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /something went wrong/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reload/i })).toBeInTheDocument();
  });

  it("keeps the error message reachable without putting a stack on screen", async () => {
    render(
      <ErrorBoundary>
        <Explodes />
      </ErrorBoundary>
    );

    // Behind a <details>, so it's there to quote in a bug report without
    // being the first thing a learner sees.
    await userEvent.click(screen.getByText("Technical details"));
    expect(
      screen.getByText(/Cannot read properties of undefined/)
    ).toBeInTheDocument();
  });

  it("logs the component stack, which is the part that locates the failure", () => {
    render(
      <ErrorBoundary>
        <Explodes />
      </ErrorBoundary>
    );

    const logged = (console.error as ReturnType<typeof vi.fn>).mock.calls;
    expect(
      logged.some((args) => args[0] === "Unhandled render error:")
    ).toBe(true);
  });
});
