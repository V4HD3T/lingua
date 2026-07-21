// Separate from vite.config.ts on purpose: the build config stays exactly
// what production uses, and vitest brings its own vite internally (no
// version coupling with the app's Vite 8).
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false, // class names aren't asserted on; queries go through roles/labels
  },
});
