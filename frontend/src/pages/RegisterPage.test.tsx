import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RegisterPage } from "./RegisterPage";
import { LEARNER, renderPage } from "../test/harness";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";

/**
 * Registration is two calls wearing one button: create the account, then
 * log straight into it. Both halves matter -- an account created without
 * the follow-up login drops the person back on a form with no hint that
 * it worked.
 */

describe("RegisterPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(Intl, "DateTimeFormat").mockReturnValue({
      resolvedOptions: () => ({ timeZone: LEARNER.timezone }),
    } as unknown as Intl.DateTimeFormat);
  });

  async function fillForm(password: string) {
    await userEvent.type(screen.getByLabelText("Username"), "ada");
    await userEvent.type(screen.getByLabelText("Email"), "ada@example.com");
    await userEvent.type(screen.getByLabelText("Password"), password);
    await userEvent.selectOptions(screen.getByLabelText("Your native language"), "tr");
    await userEvent.click(screen.getByRole("button", { name: "Sign up" }));
  }

  it("creates the account and signs in with the same credentials", async () => {
    const register = vi.spyOn(authApi, "register").mockResolvedValue(LEARNER);
    const login = vi.spyOn(authApi, "login").mockResolvedValue({
      access_token: "access-token",
      refresh_token: "refresh-token",
      token_type: "bearer",
    });
    vi.spyOn(authApi, "fetchCurrentUser").mockResolvedValue(LEARNER);

    renderPage(<RegisterPage />, {
      path: "/register",
      extraRoutes: [{ path: "/", element: <h1>Your progress</h1> }],
    });

    await fillForm("correct horse");

    expect(register).toHaveBeenCalledWith({
      username: "ada",
      email: "ada@example.com",
      password: "correct horse",
      native_language: "tr",
    });
    await screen.findByRole("heading", { name: "Your progress" });
    expect(login).toHaveBeenCalledWith("ada", "correct horse");
  });

  it("surfaces a taken username instead of pretending the signup worked", async () => {
    vi.spyOn(authApi, "register").mockRejectedValue(
      new ApiError("Username already registered", 400)
    );
    const login = vi.spyOn(authApi, "login");

    renderPage(<RegisterPage />, {
      path: "/register",
      extraRoutes: [{ path: "/", element: <h1>Your progress</h1> }],
    });

    await fillForm("correct horse");

    await screen.findByText("Username already registered");
    expect(login).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Sign up" })).toBeEnabled();
  });
});
