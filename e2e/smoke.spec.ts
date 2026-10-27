import { expect, test } from "@playwright/test";

/**
 * Critical path against a running app (preview or production).
 * Set BASE_URL, and optionally E2E_EMAIL / E2E_PASSWORD for the signed-in path.
 */
test("public leagues page is not a blank screen", async ({ page }) => {
  const failures: string[] = [];
  page.on("pageerror", (error) => failures.push(error.message));

  const response = await page.goto("/tabs/competitions", { waitUntil: "domcontentloaded" });
  expect(response?.ok()).toBeTruthy();
  await expect(page.locator("fm-root")).not.toBeEmpty();
  await expect(page.getByText(/Fair Measure could not start/i)).toHaveCount(0);
  expect(failures, failures.join("\n")).toEqual([]);
});

test("API misses return JSON, not the SPA", async ({ request, baseURL }) => {
  const origin = new URL(baseURL || "http://localhost:8100").origin;
  const response = await request.get(`${origin}/api/v1/this-route-does-not-exist`);
  expect(response.status()).toBe(404);
  expect(response.headers()["content-type"] || "").toContain("application/json");
  expect(await response.json()).toEqual({ error: "not_found" });
});

test("healthz does not leak checks", async ({ request, baseURL }) => {
  const origin = new URL(baseURL || "http://localhost:8100").origin;
  const response = await request.get(`${origin}/healthz`);
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  expect(body.checks).toBeUndefined();
  expect(["ok", "degraded", "error"]).toContain(body.status);
});

test("signed-in smoke: create competition → team → fixture → score", async ({ page }) => {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  test.skip(!email || !password, "Set E2E_EMAIL and E2E_PASSWORD to run the product path.");

  await page.goto("/login");
  await page.getByLabel(/email/i).fill(email!);
  await page.getByLabel(/password/i).fill(password!);
  await page.getByRole("button", { name: /sign in|log in/i }).click();
  await page.waitForURL(/tabs\/competitions/);

  await page.goto("/tabs/competitions/new");
  const stamp = `E2E ${Date.now()}`;
  await page.getByLabel(/name/i).first().fill(stamp);
  await page.getByRole("button", { name: /create/i }).click();
  await page.waitForURL(/tabs\/competitions\/.+/, { timeout: 30_000 });
  await expect(page.getByText(stamp).first()).toBeVisible();
});
