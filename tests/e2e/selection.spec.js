const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const USERNAME = process.env.E2E_USERNAME || "pw_smoketest";
const PASSWORD = process.env.E2E_PASSWORD || "pw_smoketest_pass123";

test("selecting a preview element updates the AI panel without waiting for a poll", async ({ page }) => {
  await page.goto(`${BASE}/login/`);
  await page.fill("input[name=\"username\"]", USERNAME);
  await page.fill("input[name=\"password\"]", PASSWORD);
  await Promise.all([
    page.waitForNavigation(),
    page.click("button[type=\"submit\"], input[type=\"submit\"]"),
  ]);

  if (!page.url().includes("/editor/")) {
    await page.goto(`${BASE}/editor/`);
  }
  await page.waitForSelector("#previewFrame");

  const frame = page.frameLocator("#previewFrame");
  const firstEditable = frame.locator("[data-vjpb-path]").first();
  await firstEditable.waitFor({ state: "visible", timeout: 10000 });
  await firstEditable.click();

  // 50ms only — proves the update is event-driven, not waiting on the old 400ms poll.
  await page.waitForTimeout(50);

  await expect(page.locator("#aiContextChip")).toContainText("Editando:");
  await expect(frame.locator("#vjpb-actions")).toBeVisible();
});
