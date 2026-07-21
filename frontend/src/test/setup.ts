// Registers the jest-dom matchers on vitest's expect (the import also
// carries the TypeScript augmentation project-wide, since this file is
// inside src/ and therefore part of the tsc -b compilation).
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  localStorage.clear();
  // Theme tests set this on the real document root; never leak it.
  delete document.documentElement.dataset.theme;
});
