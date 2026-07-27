import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { NotFoundPage } from "./NotFoundPage";
import { renderPage } from "../test/harness";

/**
 * Before the catch-all route existed, an unknown address matched no route
 * and `<Routes>` rendered nothing: nav bar, then an empty `<main>`. That
 * reads as a page that failed to load rather than one that isn't there,
 * and a stale bookmark or a mistyped URL both landed on it (v0.1.21).
 */

describe("NotFoundPage", () => {
  it("says the page doesn't exist rather than showing nothing", () => {
    renderPage(<NotFoundPage />, { path: "*", entry: "/no-such-place" });

    expect(
      screen.getByRole("heading", { name: /doesn't exist/i })
    ).toBeInTheDocument();
  });

  it("points somewhere, since a dead end is only useful if it does", () => {
    renderPage(<NotFoundPage />, { path: "*", entry: "/no-such-place" });

    expect(screen.getByRole("link", { name: "Translate" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Courses" })).toHaveAttribute(
      "href",
      "/courses"
    );
    expect(screen.getByRole("link", { name: "Review" })).toHaveAttribute(
      "href",
      "/review"
    );
  });
});
