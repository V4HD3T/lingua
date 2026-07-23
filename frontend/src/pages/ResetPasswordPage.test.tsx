import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResetPasswordPage } from "./ResetPasswordPage";
import { renderPage } from "../test/harness";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";

/**
 * Reset tokens are single-use and expire, so "this link is spent" is a
 * routine outcome rather than an edge case -- it has to be said in a way
 * that leads somewhere. The no-token case is a separate branch: without
 * one there is nothing to submit, so the form isn't offered at all.
 */

function renderReset(search: string) {
  return renderPage(<ResetPasswordPage />, {
    path: "/reset-password",
    entry: `/reset-password${search}`,
  });
}

describe("ResetPasswordPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("sends the new password with the token from the link", async () => {
    const reset = vi
      .spyOn(authApi, "resetPassword")
      .mockResolvedValue({ message: "Password updated. You can log in now." });

    renderReset("?token=fresh");

    await userEvent.type(screen.getByLabelText("New password"), "correct horse");
    await userEvent.click(screen.getByRole("button", { name: "Save new password" }));

    expect(reset).toHaveBeenCalledWith("fresh", "correct horse");
    await screen.findByText("Password updated. You can log in now.");
    expect(screen.getByRole("link", { name: "Go to login" })).toHaveAttribute("href", "/login");
    expect(screen.queryByLabelText("New password")).not.toBeInTheDocument();
  });

  it("passes on the server's verdict when the token is spent or expired", async () => {
    vi.spyOn(authApi, "resetPassword").mockRejectedValue(
      new ApiError("Invalid or expired reset token", 400)
    );

    renderReset("?token=stale");

    await userEvent.type(screen.getByLabelText("New password"), "correct horse");
    await userEvent.click(screen.getByRole("button", { name: "Save new password" }));

    await screen.findByText("Invalid or expired reset token");
    // Still on the form: a fresh link lands the person right back here.
    expect(screen.getByLabelText("New password")).toBeInTheDocument();
  });

  it("offers a new link instead of a form when the token is missing", async () => {
    const reset = vi.spyOn(authApi, "resetPassword");

    renderReset("");

    await screen.findByText(/missing its token/);
    expect(screen.queryByLabelText("New password")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Request a new link" })).toHaveAttribute(
      "href",
      "/forgot-password"
    );
    expect(reset).not.toHaveBeenCalled();
  });
});
