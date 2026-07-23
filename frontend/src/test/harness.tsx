// Shared scaffolding for the page tests. Pages are the layer where router,
// auth context, toasts and the API modules all meet, so rendering one in
// isolation means standing that stack up every time -- this keeps the tests
// themselves about behaviour rather than about wiring.
import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import { AuthProvider } from "../context/AuthContext";
import { ToastProvider } from "../context/ToastContext";
import * as authApi from "../api/auth";
import { setTokens } from "../api/client";
import type { User } from "../types";

export const LEARNER: User = {
  id: 1,
  username: "ada",
  email: "ada@example.com",
  native_language: "en",
  timezone: "Europe/Istanbul",
  daily_review_goal: 10,
  is_verified: true,
  is_admin: false,
};

/**
 * Puts a signed-in learner behind the AuthProvider: a stored token (which
 * is what makes the provider fetch at all) plus the /auth/me answer.
 *
 * The timezone is pinned to the fixture's so AuthContext's zone reporting
 * stays out of the way -- it has its own tests, and an unmocked
 * updateTimezone here would just be noise.
 */
export function signIn(overrides: Partial<User> = {}): User {
  const user = { ...LEARNER, ...overrides };
  setTokens("access-token", "refresh-token");
  vi.spyOn(Intl, "DateTimeFormat").mockReturnValue({
    resolvedOptions: () => ({ timeZone: user.timezone }),
  } as unknown as Intl.DateTimeFormat);
  vi.spyOn(authApi, "fetchCurrentUser").mockResolvedValue(user);
  return user;
}

interface RouteOptions {
  /** Route pattern the page is mounted at, e.g. "/lessons/:lessonId/quiz". */
  path?: string;
  /** Address to start at; must match `path`. */
  entry?: string;
  /** Extra routes to land on, so navigation away is observable. */
  extraRoutes?: Array<{ path: string; element: ReactElement }>;
}

export function renderPage(page: ReactElement, options: RouteOptions = {}) {
  const { path = "/", entry = path, extraRoutes = [] } = options;
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path={path} element={page} />
            {extraRoutes.map((route) => (
              <Route key={route.path} path={route.path} element={route.element} />
            ))}
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </MemoryRouter>
  );
}
