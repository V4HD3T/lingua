import { apiRequest } from "./client";
import type { UserStats } from "../types";

export function fetchMyStats(): Promise<UserStats> {
  return apiRequest<UserStats>("/users/me/stats", { auth: true });
}
