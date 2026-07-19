import { apiRequest } from "./client";
import type { User } from "../types";

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  native_language: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export function register(payload: RegisterPayload): Promise<User> {
  return apiRequest<User>("/auth/register", { method: "POST", body: payload });
}

export function login(username: string, password: string): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    form: { username, password },
  });
}

export function logout(refreshToken: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/logout", {
    method: "POST",
    body: { refresh_token: refreshToken },
  });
}

export function logoutAllSessions(): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/logout-all", { method: "POST", auth: true });
}

export function fetchCurrentUser(): Promise<User> {
  return apiRequest<User>("/auth/me", { auth: true });
}

export function updateDailyGoal(dailyGoal: number): Promise<User> {
  return apiRequest<User>("/auth/me/goal", {
    method: "PATCH",
    body: { daily_goal: dailyGoal },
    auth: true,
  });
}

export function requestPasswordReset(email: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/request-password-reset", {
    method: "POST",
    body: { email },
  });
}

export function resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/reset-password", {
    method: "POST",
    body: { token, new_password: newPassword },
  });
}

export function verifyEmail(token: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/verify-email", {
    method: "POST",
    body: { token },
  });
}
