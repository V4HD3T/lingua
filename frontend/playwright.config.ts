import { defineConfig } from "@playwright/test";

// E2E against the REAL stack: Playwright boots the actual FastAPI backend
// (fresh throwaway SQLite + seeded content) and the Vite dev server, then
// drives a real Chromium through the full learner journey. Selectors lean
// on the v0.1.1 accessibility work (labels, roles, fieldset legends) --
// the a11y round paying for itself as testability.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "on-first-retry",
  },
  webServer: [
    {
      // rm first: each run starts from the seeded state, so quiz answers
      // and adaptive behaviour stay deterministic.
      command:
        "rm -f /tmp/lingua-e2e.db && cd ../backend && DATABASE_URL=sqlite:////tmp/lingua-e2e.db uvicorn app.main:app --port 8000",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npm run dev -- --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
