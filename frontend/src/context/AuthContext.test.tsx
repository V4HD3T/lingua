import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "./AuthContext";
import * as authApi from "../api/auth";
import { setTokens } from "../api/client";
import type { User } from "../types";

/**
 * v0.1.9. The server counts streaks, "reviews today" and review
 * scheduling against the learner's own calendar day, so it has to know
 * where they are. The browser already knows, so this is reported rather
 * than asked for -- a settings field nobody fills in would leave most
 * accounts on the wrong calendar.
 *
 * Two properties worth holding: it doesn't spend a request when the
 * server already agrees, and it can never be the reason someone fails to
 * get in.
 */

function userWith(timezone: string): User {
  return {
    id: 1,
    username: "learner",
    email: "learner@example.com",
    native_language: "en",
    timezone,
    daily_review_goal: 10,
    is_verified: true,
    is_admin: false,
  };
}

function Probe() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <span>loading</span>;
  return <span data-testid="zone">{user ? user.timezone : "anonymous"}</span>;
}

function renderApp() {
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>
  );
}

describe("AuthContext timezone reporting", () => {
  beforeEach(() => {
    setTokens("access", "refresh");
    vi.restoreAllMocks();
    vi.spyOn(Intl, "DateTimeFormat").mockReturnValue({
      resolvedOptions: () => ({ timeZone: "Europe/Istanbul" }),
    } as unknown as Intl.DateTimeFormat);
  });

  it("reports the browser zone when the server disagrees", async () => {
    vi.spyOn(authApi, "fetchCurrentUser").mockResolvedValue(userWith("UTC"));
    const update = vi
      .spyOn(authApi, "updateTimezone")
      .mockResolvedValue(userWith("Europe/Istanbul"));

    renderApp();

    await waitFor(() => expect(screen.getByTestId("zone")).toHaveTextContent("Europe/Istanbul"));
    expect(update).toHaveBeenCalledWith("Europe/Istanbul");
  });

  it("stays quiet when the server already has the right zone", async () => {
    vi.spyOn(authApi, "fetchCurrentUser").mockResolvedValue(userWith("Europe/Istanbul"));
    const update = vi.spyOn(authApi, "updateTimezone");

    renderApp();

    await waitFor(() => expect(screen.getByTestId("zone")).toHaveTextContent("Europe/Istanbul"));
    expect(update).not.toHaveBeenCalled();
  });

  it("still signs the user in when reporting the zone fails", async () => {
    // Being on the wrong calendar beats not getting in.
    vi.spyOn(authApi, "fetchCurrentUser").mockResolvedValue(userWith("UTC"));
    vi.spyOn(authApi, "updateTimezone").mockRejectedValue(new Error("network"));

    renderApp();

    await waitFor(() => expect(screen.getByTestId("zone")).toHaveTextContent("UTC"));
  });
});
