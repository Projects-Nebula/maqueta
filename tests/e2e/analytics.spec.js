const { test, expect } = require("@playwright/test");

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const USERNAME = process.env.E2E_USERNAME || "pw_smoketest";
const PASSWORD = process.env.E2E_PASSWORD || "pw_smoketest_pass123";

async function login(page) {
  await page.goto(`${BASE}/login/`);
  await page.fill('input[name="username"]', USERNAME);
  await page.fill('input[name="password"]', PASSWORD);
  await Promise.all([page.waitForNavigation(), page.click('button[type="submit"]')]);
}

async function createPublishedTemplate(page) {
  const result = await page.evaluate(async () => {
    const csrf = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith("csrftoken="))
      ?.split("=")[1];
    const state = {
      document: {
        head: { title: "Analytics browser check", metas: [], links: [], scripts: [] },
        htmlAttributes: { lang: "en", dir: "ltr" },
        doctype: "html",
        body: {
          attributes: {},
          children: [
            {
              type: "element",
              tag: "h1",
              attributes: {},
              children: [{ type: "text", value: "Analytics browser check" }],
            },
          ],
        },
      },
      styles: { variables: {}, rules: [], mediaQueries: [], keyframes: [] },
      components: {},
      assets: {},
    };
    const createResponse = await fetch("/api/user-templates/", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify({ name: "Analytics browser check", state }),
    });
    const created = await createResponse.json();
    if (!createResponse.ok) throw new Error(JSON.stringify(created));
    const publishResponse = await fetch(`/api/user-templates/${created.id}/publish/`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrf },
    });
    const published = await publishResponse.json();
    if (!publishResponse.ok) throw new Error(JSON.stringify(published));
    return { id: created.id, slug: published.public_slug };
  });
  return result;
}

async function deleteTemplate(page, id) {
  await page.evaluate(async (templateId) => {
    const csrf = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith("csrftoken="))
      ?.split("=")[1];
    await fetch(`/api/user-templates/${templateId}/`, {
      method: "DELETE",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrf },
    });
  }, id);
}

test("analytics dashboard loads owner-scoped controls and empty states", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/analytics/`);

  await expect(page).toHaveTitle("Analítica de visitas");
  await expect(page.locator("h1")).toHaveText("Analítica de visitas");
  await expect(page.locator("#analyticsTemplate")).toBeVisible();
  await expect(page.locator("#analyticsDays")).toHaveValue("30");
  await expect(page.locator("#metricVisitors")).toHaveText("0");
  await expect(page.locator("#sessionsEmpty")).toBeVisible();
  await expect(page.locator("#heatmapEmpty")).toBeVisible();
  await expect(page.locator("#analyticsRefresh")).toBeEnabled();
});

test("analytics dashboard remains usable on a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await login(page);
  await page.goto(`${BASE}/analytics/`);

  await expect(page.locator("#analyticsRefresh")).toBeVisible();
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(320);
});

test("published pages ask for analytics consent before identifying a visitor", async ({ page }) => {
  await login(page);
  const template = await createPublishedTemplate(page);
  try {
    await page.goto(`${BASE}/t/${template.slug}/`);
    await expect(page.locator("#analyticsConsent")).toBeVisible();
    expect(await page.evaluate(() => document.cookie)).not.toContain("analytics_visitor_id=");

    await page.locator(".analytics-consent-decline").click();
    await expect(page.locator("#analyticsConsent")).toHaveCount(0);
    expect(await page.evaluate(() => document.cookie)).toContain("analytics_consent=declined");
    expect(await page.evaluate(() => document.cookie)).not.toContain("analytics_visitor_id=");
  } finally {
    await deleteTemplate(page, template.id);
  }
});
