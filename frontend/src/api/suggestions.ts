import { apiRequest } from "./client";
import type { VocabularySuggestion } from "../types";

export function getVocabularySuggestions(): Promise<VocabularySuggestion[]> {
  return apiRequest<VocabularySuggestion[]>("/users/me/vocabulary-suggestions", {
    auth: true,
  });
}
