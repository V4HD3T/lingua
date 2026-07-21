import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "./ThemeContext";
import { ThemeToggle } from "../components/ThemeToggle";

function renderToggle() {
  return render(
    <ThemeProvider>
      <ThemeToggle />
    </ThemeProvider>
  );
}

describe("ThemeContext + ThemeToggle", () => {
  it("toggles the document theme attribute and its own label", async () => {
    renderToggle();
    const button = screen.getByRole("button", { name: "Switch to dark theme" });

    await userEvent.click(button);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toBeInTheDocument();

    await userEvent.click(button);
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("persists to storage ONLY on an explicit toggle", async () => {
    renderToggle();
    // just rendering must not lock the user to a stored snapshot
    expect(localStorage.getItem("lingua_theme")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: /dark theme/ }));
    expect(localStorage.getItem("lingua_theme")).toBe("dark");
  });

  it("picks up the theme the pre-paint script already applied", () => {
    document.documentElement.dataset.theme = "dark";
    renderToggle();
    expect(screen.getByRole("button", { name: "Switch to light theme" })).toBeInTheDocument();
  });
});
