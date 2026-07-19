import { apiRequest } from "./client";
import type { Achievement } from "../types";

export function getMyAchievements(): Promise<Achievement[]> {
  return apiRequest<Achievement[]>("/users/me/achievements", { auth: true });
}
