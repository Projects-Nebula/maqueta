const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const USERNAME = process.env.E2E_USERNAME || "pw_smoketest";
const PASSWORD = process.env.E2E_PASSWORD || "pw_smoketest_pass123";
const TOKEN_HREF = "/static/shared/tokens.css";

test("all server-rendered UI surfaces use the shared token stylesheet", async ({ page }) => {
  for (const path of ["/login/", "/cancelado/", "/gracias/?gateway=stripe&session_id=ui-smoke"]) {
    await page.goto(`${BASE}${path}`);
    await expect(page.locator(`link[href="${TOKEN_HREF}"]`)).toHaveCount(1);
  }

  await page.goto(`${BASE}/login/`);
  await page.fill('input[name="username"]', USERNAME);
  await page.fill('input[name="password"]', PASSWORD);
  await Promise.all([
    page.waitForNavigation(),
    page.click('button[type="submit"]'),
  ]);

  for (const path of ["/editor/", "/home/", "/gallery/", "/productos/", "/config/", "/wizard/"]) {
    await page.goto(`${BASE}${path}`);
    await expect(page.locator(`link[href="${TOKEN_HREF}"]`)).toHaveCount(1);
  }

  await page.goto(`${BASE}/login/`);
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(238, 242, 247)");
  await expect(page.locator("body")).toHaveCSS("font-family", /Inter/);
});
