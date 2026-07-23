import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ForgotPasswordPage } from "./ForgotPasswordPage";
import { renderPage } from "../test/harness";
import * as authApi from "../api/auth";

/**
 * The backend answers this one identically whether or not the address is
 * on file (it must not become an account-existence oracle -- SECURITY.md,
 * A01). The page's part of that bargain is to show the server's message as
 * given and stop offering the form, so nothing on screen hints at which
 * kind of address was typed.
 */

const NEUTRAL = "If that email is registered, a reset link has been sent.";

describe("ForgotPasswordPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("relays the server's neutral answer and retires the form", async () => {
    const request = vi
      .spyOn(authApi, "requestPasswordReset")
      .mockResolvedValue({ message: NEUTRAL });

    renderPage(<ForgotPasswordPage />);

    await userEvent.type(screen.getByLabelText("Email"), "ada@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(request).toHaveBeenCalledWith("ada@example.com");
    await screen.findByText(NEUTRAL);
    expect(screen.queryByRole("button", { name: "Send reset link" })).not.toBeInTheDocument();
  });

  it("leaves the form usable when the request itself fails", async () => {
    vi.spyOn(authApi, "requestPasswordReset").mockRejectedValue(new Error("network"));

    renderPage(<ForgotPasswordPage />);

    await userEvent.type(screen.getByLabelText("Email"), "ada@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    await screen.findByText("Something went wrong");
    expect(screen.getByRole("button", { name: "Send reset link" })).toBeEnabled();
  });
});
