import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { VerifyEmailPage } from "./VerifyEmailPage";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";

/**
 * The regression this locks down (v0.1.12): verification tokens are
 * single-use server-side, and StrictMode runs mount effects twice in
 * development. Without the request guard the second POST found the token
 * already spent, and the resulting 400 overwrote the first call's success
 * -- the email really was verified, but the page said the link was
 * invalid. Rendering inside StrictMode is the point of this file.
 */

function renderVerify(search: string) {
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={[`/verify-email${search}`]}>
        <Routes>
          <Route path="/verify-email" element={<VerifyEmailPage />} />
        </Routes>
      </MemoryRouter>
    </StrictMode>
  );
}

describe("VerifyEmailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("spends the single-use token exactly once, even under StrictMode", async () => {
    const verify = vi
      .spyOn(authApi, "verifyEmail")
      .mockResolvedValue({ message: "Email verified" });

    renderVerify("?token=one-shot");

    await screen.findByText("Your email has been verified ✓");
    expect(verify).toHaveBeenCalledTimes(1);
    expect(verify).toHaveBeenCalledWith("one-shot");
  });

  it("explains a genuinely dead link", async () => {
    vi.spyOn(authApi, "verifyEmail").mockRejectedValue(
      new ApiError("Invalid or expired verification token", 400)
    );

    renderVerify("?token=stale");

    await screen.findByText("Invalid or expired verification token");
  });

  it("doesn't call the API at all when the link arrives without a token", async () => {
    const verify = vi.spyOn(authApi, "verifyEmail");

    renderVerify("");

    await screen.findByText(/missing its token/);
    expect(verify).not.toHaveBeenCalled();
  });
});
