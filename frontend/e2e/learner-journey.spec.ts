import { expect, test } from "@playwright/test";

const BACKEND = "http://127.0.0.1:8000";

// One long journey on purpose: the point of E2E here is the seams between
// pages and the real backend (token flow, session-graded quiz, history),
// not isolated widgets -- those live in the Vitest suite.
test("full learner journey: login → translate → quiz (100%) → history → dark mode", async ({
  page,
  request,
}) => {
  // Register through the API, not the form: keeps the test independent of
  // register-page copy, and email verification isn't required for login.
  const username = `e2e_${Date.now().toString(36)}`;
  const password = "password1234";
  const registered = await request.post(`${BACKEND}/auth/register`, {
    data: { username, email: `${username}@example.com`, password },
  });
  expect(registered.ok()).toBeTruthy();

  // --- login through the real form ---
  await page.goto("/login");
  await page.getByLabel(/username/i).fill(username);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole("button", { name: /log in/i }).click();

  // --- translate; the saved-notice doubles as proof the session works ---
  await page.goto("/");
  await page.getByLabel("Text to translate").fill("hello world");
  const output = page.getByRole("status").filter({ hasText: "[en->es] hello world" });
  await expect(output).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Saved to your translation history")).toBeVisible();

  // --- quiz: first attempt serves all five seeded questions ---
  await page.goto("/lessons/1/quiz");
  const group = (n: number) => page.getByRole("group", { name: new RegExp(`^${n}\\.`) });

  await group(1).getByRole("radio", { name: "hello" }).check();
  await group(2).getByRole("radio", { name: "goodbye" }).check();
  await group(3).getByPlaceholder("Type your answer...").fill("hola");
  await group(4).getByRole("radio", { name: "hola" }).check();
  for (const word of ["hola", "como", "estas"]) {
    await group(5).getByRole("button", { name: word }).click();
  }
  await page.getByRole("button", { name: /submit answers/i }).click();

  await expect(page.getByText("100%")).toBeVisible();
  await expect(page.getByText("5 out of 5")).toBeVisible();

  // --- history shows the translation ---
  await page.goto("/history");
  await expect(page.getByText("hello world")).toBeVisible();
  await expect(page.getByText("[en->es] hello world")).toBeVisible();

  // --- dark mode toggles the document theme ---
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});
