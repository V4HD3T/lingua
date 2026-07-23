// Registers the jest-dom matchers on vitest's expect (the import also
// carries the TypeScript augmentation project-wide, since this file is
// inside src/ and therefore part of the tsc -b compilation).
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Node >= 24 defines a global `localStorage` of its own that stays inert
// unless the process was started with --localstorage-file. vitest's jsdom
// environment only copies window properties globalThis doesn't already
// have, so that inert binding shadows jsdom's real Storage and every
// localStorage call dies with "Cannot read properties of undefined".
// Node 22 (what CI runs) keeps Web Storage behind a flag and is unaffected
// -- which is exactly why this has to be handled here rather than noticed
// on a green pipeline. An in-memory Storage keeps the suite working on
// both, and matches the only semantics the app relies on.
if (typeof globalThis.localStorage === "undefined") {
  const items = new Map<string, string>();
  const memoryStorage: Storage = {
    get length() {
      return items.size;
    },
    clear: () => items.clear(),
    getItem: (key) => items.get(key) ?? null,
    key: (index) => [...items.keys()][index] ?? null,
    removeItem: (key) => {
      items.delete(key);
    },
    setItem: (key, value) => {
      items.set(String(key), String(value));
    },
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: memoryStorage,
    configurable: true,
    writable: true,
  });
}

afterEach(() => {
  cleanup();
  localStorage.clear();
  // Theme tests set this on the real document root; never leak it.
  delete document.documentElement.dataset.theme;
});
