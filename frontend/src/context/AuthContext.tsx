import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import * as authApi from "../api/auth";
import { ApiError, clearTokens, getAccessToken, getRefreshToken, setTokens } from "../api/client";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (
    username: string,
    email: string,
    password: string,
    nativeLanguage: string
  ) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * Tells the backend where the learner is, so their day starts and ends
 * where they do (v0.1.9). Streaks, "reviews today" and review scheduling
 * are all counted against it; before this the server counted in UTC, and
 * a session at 01:00 in UTC+3 landed on the previous day.
 *
 * Reported rather than asked for: the browser already knows, and a
 * settings field nobody fills in would leave most accounts on the wrong
 * calendar. Sent only when it actually differs from what the server has,
 * so the ordinary page load costs no extra request -- and never allowed to
 * break sign-in, since being on the wrong calendar beats not getting in.
 */
async function reportTimezone(user: User): Promise<User> {
  const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  if (!browserZone || browserZone === user.timezone) return user;
  try {
    return await authApi.updateTimezone(browserZone);
  } catch {
    return user;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setIsLoading(false);
      return;
    }
    authApi
      .fetchCurrentUser()
      .then(reportTimezone)
      .then(setUser)
      .catch((err) => {
        // Only discard the session when the backend actually rejected it.
        // fetch() also throws on network failure (backend down, restarting,
        // no connection) — logging the user out for that would mean every
        // API blip on page load silently destroyed a valid session.
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          clearTokens();
        }
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function login(username: string, password: string) {
    const { access_token, refresh_token } = await authApi.login(username, password);
    setTokens(access_token, refresh_token);
    const me = await authApi.fetchCurrentUser();
    setUser(await reportTimezone(me));
  }

  async function register(
    username: string,
    email: string,
    password: string,
    nativeLanguage: string
  ) {
    await authApi.register({
      username,
      email,
      password,
      native_language: nativeLanguage,
    });
    await login(username, password);
  }

  async function logout() {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      // Best-effort: revoke server-side so the refresh token can't be used
      // again even if someone got hold of it. Still clear local state even
      // if this call fails (e.g. offline) -- the person clicked "log out"
      // and expects to be logged out locally regardless.
      try {
        await authApi.logout(refreshToken);
      } catch {
        // ignore -- local logout proceeds either way
      }
    }
    clearTokens();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
