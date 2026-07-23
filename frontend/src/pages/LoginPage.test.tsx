import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginPage } from "./LoginPage";
import { LEARNER, renderPage } from "../test/harness";
import * as authApi from "../api/auth";
import { ApiError, getAccessToken } from "../api/client";

/**
 * The login form's job is small but unforgiving: hand the credentials to
 * the auth context, leave on success, and on failure say why *and* let the
 * person try again. That last part is the one that quietly breaks -- a
 * submit flag that isn't reset leaves a permanently disabled button after
 * a single typo.
 */

function dashboard() {
  return { path: "/", element: <h1>Your progress</h1> };
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(Intl, "DateTimeFormat").mockReturnValue({
      resolvedOptions: () => ({ timeZone: LEARNER.timezone }),
    } as unknown as Intl.DateTimeFormat);
  });

  it("signs the learner in and moves on to the app", async () => {
    const login = vi.spyOn(authApi, "login").mockResolvedValue({
      access_token: "access-token",
      refresh_token: "refresh-token",
      token_type: "bearer",
    });
    vi.spyOn(authApi, "fetchCurrentUser").mockResolvedValue(LEARNER);

    renderPage(<LoginPage />, { path: "/login", extraRoutes: [dashboard()] });

    await userEvent.type(screen.getByLabelText("Username"), "ada");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect(login).toHaveBeenCalledWith("ada", "correct horse");
    await screen.findByRole("heading", { name: "Your progress" });
    // The session has to survive a reload, not just this render.
    expect(getAccessToken()).toBe("access-token");
  });

  it("shows the server's reason and leaves the form usable after a rejection", async () => {
    vi.spyOn(authApi, "login").mockRejectedValue(
      new ApiError("Incorrect username or password", 401)
    );

    renderPage(<LoginPage />, { path: "/login", extraRoutes: [dashboard()] });

    await userEvent.type(screen.getByLabelText("Username"), "ada");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    await screen.findByText("Incorrect username or password");
    expect(screen.queryByRole("heading", { name: "Your progress" })).not.toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Log in" })).toBeEnabled()
    );
    expect(getAccessToken()).toBeNull();
  });

  it("falls back to a plain message when the failure isn't from the API", async () => {
    vi.spyOn(authApi, "login").mockRejectedValue(new TypeError("Failed to fetch"));

    renderPage(<LoginPage />, { path: "/login", extraRoutes: [dashboard()] });

    await userEvent.type(screen.getByLabelText("Username"), "ada");
    await userEvent.type(screen.getByLabelText("Password"), "correct horse");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    // Never the raw network error -- it says nothing to the person reading it.
    await screen.findByText("Couldn't log in");
  });
});
