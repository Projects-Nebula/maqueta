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

test("editor provides a visible route back to the template gallery", async ({ page }) => {
  await login(page);
  const exitLink = page.locator("a.editor-exit");
  await expect(exitLink).toBeVisible();
  await expect(exitLink).toHaveText(/Salir/);
  await expect(exitLink).toHaveAttribute("href", "/gallery/");
  await exitLink.click();
  await expect(page).toHaveURL(/\/gallery\/$/);
});

test("quick-insert presets render styled sections", async ({ page }) => {
  await login(page);
  await page.locator('.section-open[data-section="content"]').click();
  const modal = page.locator("#sectionModal");
  await expect(modal).toBeVisible();

  const frame = page.frameLocator("#previewFrame");
  await modal.locator('[data-preset="hero"]').click();
  await expect(frame.locator("section.bg-gray-50").last()).toBeVisible();

  await modal.locator('[data-preset="image"]').click();
  await expect(frame.locator('img.rounded-2xl').last()).toBeVisible();

  await modal.locator('[data-preset="cta"]').click();
  await expect(frame.locator("section .bg-indigo-600").last()).toBeVisible();
});

test("AI assistant edits a legacy-class preview node", async ({ page }) => {
  await login(page);

  await page.frameLocator("#previewFrame").locator("header").click();
  await page.locator("#aiFab").click();
  await expect(page.locator("#aiDrawer")).toBeVisible();

  await page.locator("#aiComposerInput").fill("Mejora la visibilidad de esta sección");
  await page.locator("#aiComposerSend").click();

  await expect(page.locator("#aiMessages .ai-bubble-note").last()).toHaveText(
    "✓ Aplicado",
    { timeout: 15000 }
  );
  await expect(page.locator("#aiMessages .ai-bubble-error")).toHaveCount(0);
});

test("palette presets apply as one undoable change and support custom colors", async ({ page }) => {
  await login(page);
  await page.locator('.section-open[data-section="design"]').click();
  await expect(page.locator("#palettePresetSelect")).toBeVisible();
  await expect(page.locator("#paletteSwatches .palette-swatch")).toHaveCount(4);

  await page.locator("#palettePresetSelect").selectOption("ocean");
  await expect(page.locator("#paletteStatus")).toHaveText("Océano");
  let palette = await page.evaluate(() => window.EditorCore.getState().styles);
  expect(palette.palette).toEqual({ id: "ocean", name: "Océano", source: "preset" });
  expect(palette.variables["--color-primary"]).toBe("#0f766e");

  await page.locator("#sectionModalClose").click();
  await page.locator("#undoButton").click();
  palette = await page.evaluate(() => window.EditorCore.getState().styles);
  expect(palette.variables["--color-primary"]).not.toBe("#0f766e");

  await page.locator('.section-open[data-section="design"]').click();
  await page.locator("#paletteName").fill("Mi marca");
  await page.locator("#primaryColor").fill("#112233");
  await expect.poll(async () => {
    const styles = await page.evaluate(() => window.EditorCore.getState().styles);
    return styles.palette && styles.palette.source;
  }).toBe("custom");
  palette = await page.evaluate(() => window.EditorCore.getState().styles);
  expect(palette.palette.name).toBe("Mi marca");
  expect(palette.variables["--color-primary"]).toBe("#112233");

  await page.locator("#primaryColor").fill("#fff");
  await expect(page.locator('#paletteContrast[data-tone="error"]')).toBeVisible();
  palette = await page.evaluate(() => window.EditorCore.getState().styles);
  expect(palette.variables["--color-primary"]).toBe("#112233");

  await page.locator("#sectionModal").evaluate((modal) => { modal.scrollTop = modal.scrollHeight; });
  await page.locator("#paletteResetButton").click();
  palette = await page.evaluate(() => window.EditorCore.getState().styles);
  expect(palette.variables["--color-primary"]).toBe("#5b5ce2");
});

test("palette contrast warning remains usable on a 320px viewport", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await login(page);
  await page.locator('.section-open[data-section="design"]').click();
  await page.locator("#textColor").fill("#eeeeee");
  await page.locator("#backgroundColor").fill("#ffffff");
  await expect(page.locator('#paletteContrast[data-tone="warning"]')).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
});

test("owner can save, reuse, and delete a palette from the editor", async ({ page }) => {
  await login(page);
  await page.locator('.section-open[data-section="design"]').click();
  const name = `E2E palette ${Date.now()}`;
  await page.locator("#paletteName").fill(name);
  await page.locator("#paletteSaveButton").click();

  const savedOption = page
    .locator('#palettePresetSelect optgroup[data-user-palettes="true"] option')
    .filter({ hasText: name });
  await expect(savedOption).toHaveCount(1);
  const value = await savedOption.getAttribute("value");
  await page.locator("#palettePresetSelect").selectOption(value);
  await expect(page.locator("#paletteStatus")).toHaveText(name);
  await expect(page.locator("#paletteDeleteButton")).toBeVisible();

  await page.locator("#paletteDeleteButton").click();
  await expect(savedOption).toHaveCount(0);
  await expect(page.locator("#paletteDeleteButton")).toBeHidden();
});

test("wizard exposes the same server catalog for its initial palette choice", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/wizard/`);
  const select = page.locator("#wizardPaletteSelect");
  await expect(select.locator("option")).toHaveCount(6);
  await select.selectOption("forest");
  await expect(page.locator("#wizardPalettePreview")).toContainText("Verdes naturales");
  await expect(page.locator(".wizard-palette-swatch")).toHaveCount(4);
});

test("editor dialogs close with Escape and restore the opener focus", async ({ page }) => {
  await login(page);

  const sectionOpener = page.locator('.section-open[data-section="content"]');
  await sectionOpener.click();
  await expect(page.locator("#sectionModal")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("#sectionModal")).toBeHidden();
  await expect(sectionOpener).toBeFocused();

  const saveButton = page.locator("#saveTemplateButton");
  await saveButton.click();
  await expect(page.locator("#saveTemplateModal")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("#saveTemplateModal")).toBeHidden();
  await expect(saveButton).toBeFocused();
});

test("editor and edge pages stay within a 320px viewport", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  for (const path of ["/login/", "/signup/", "/cancelado/", "/gracias/?gateway=stripe&session_id=ui-smoke"]) {
    await page.goto(`${BASE}${path}`);
    const width = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(width).toBeLessThanOrEqual(320);
  }

  await login(page);
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(320);
  await page.locator("#aiFab").click();
  await expect(page.locator("#aiDrawer")).toBeVisible();
});

test("payment configuration exposes safe credential validation controls", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/config/`);
  await expect(page.locator(".gateway-card")).toHaveCount(8);
  await expect(page.locator('.gateway-card button:has-text("Validar credenciales")')).toHaveCount(8);
  await expect(page.locator('.gateway-card button:has-text("Validar credenciales")').first()).toBeDisabled();
});
