const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const USERNAME = process.env.E2E_USERNAME || "pw_smoketest";
const PASSWORD = process.env.E2E_PASSWORD || "pw_smoketest_pass123";

async function login(page) {
  await page.goto(`${BASE}/login/`);
  await page.fill('input[name="username"]', USERNAME);
  await page.fill('input[name="password"]', PASSWORD);
  await Promise.all([page.waitForNavigation(), page.click('button[type="submit"]')]);
  await page.goto(`${BASE}/editor/`);
  await page.waitForSelector("#previewFrame");
}

test("Ctrl/Cmd+K opens the command palette and filters commands", async ({ page }) => {
  await login(page);
  await expect(page.locator("#commandPaletteOverlay")).toHaveCount(0);

  await page.keyboard.press("Control+k");
  const overlay = page.locator("#commandPaletteOverlay");
  await expect(overlay).toBeVisible();

  const input = overlay.locator("input");
  await expect(input).toBeFocused();

  await input.fill("guardar");
  await expect(overlay.getByText("Guardar", { exact: true })).toBeVisible();
  await expect(overlay.getByText("Descargar JSON", { exact: true })).toHaveCount(0);

  await page.keyboard.press("Escape");
  await expect(overlay).not.toBeVisible();
});

test("running a command from the palette clicks the matching button", async ({ page }) => {
  await login(page);
  await page.keyboard.press("Control+k");
  const overlay = page.locator("#commandPaletteOverlay");
  await overlay.locator("input").fill("guardar");
  await overlay.getByText("Guardar", { exact: true }).click();

  await expect(overlay).not.toBeVisible();
  await expect(page.locator("#saveTemplateModal")).toBeVisible();
});

test("inserting a quick-insert preset from the palette works without opening the section modal first", async ({
  page,
}) => {
  await login(page);
  await expect(page.locator("#sectionModal")).not.toBeVisible();

  await page.keyboard.press("Control+k");
  const overlay = page.locator("#commandPaletteOverlay");
  await overlay.locator("input").fill("Hero");
  await overlay.getByText("Insertar sección: Hero", { exact: true }).click();

  await expect(overlay).not.toBeVisible();
  const frame = page.frameLocator("#previewFrame");
  await expect(frame.locator("section.bg-gray-50").last()).toBeVisible();
});

test("Escape restores focus to the element that triggered the palette", async ({ page }) => {
  await login(page);
  await page.locator("#saveTemplateButton").focus();
  await expect(page.locator("#saveTemplateButton")).toBeFocused();

  await page.keyboard.press("Control+k");
  await expect(page.locator("#commandPaletteOverlay")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.locator("#commandPaletteOverlay")).not.toBeVisible();
  await expect(page.locator("#saveTemplateButton")).toBeFocused();
});

test("Tab stays trapped inside the open palette", async ({ page }) => {
  await login(page);
  await page.keyboard.press("Control+k");
  const overlay = page.locator("#commandPaletteOverlay");
  await expect(overlay).toBeVisible();

  // Tab through every focusable element inside the palette and one more —
  // focus must never land outside the overlay while it's open.
  for (let i = 0; i < 15; i++) {
    await page.keyboard.press("Tab");
    const focusedInsideOverlay = await page.evaluate(() => {
      const overlayEl = document.getElementById("commandPaletteOverlay");
      return overlayEl ? overlayEl.contains(document.activeElement) : false;
    });
    expect(focusedInsideOverlay).toBe(true);
  }
});
