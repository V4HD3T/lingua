import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import * as authApi from "../api/auth";
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "../api/client";
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
      .then(setUser)
      .catch(() => clearTokens())
      .finally(() => setIsLoading(false));
  }, []);

  async function login(username: string, password: string) {
    const { access_token, refresh_token } = await authApi.login(username, password);
    setTokens(access_token, refresh_token);
    const me = await authApi.fetchCurrentUser();
    setUser(me);
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
