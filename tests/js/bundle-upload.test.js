/* Unit tests for the "Subir sitio" folder-picker upload contract.
 *
 * Highest-risk piece of PR4: the backend (apps/editor/views.py::BundleViewSet
 * .create) treats every multipart field whose key is NOT "name" as one file,
 * keyed by its bundle-relative path. `File.webkitRelativePath` includes the
 * picked folder's own name as its first segment, so it must be stripped
 * before being used as a field key, or every upload 400s with
 * missing_entrypoint (no top-level index.html field ever arrives).
 *
 * Run with `node tests/js/bundle-upload.test.js` (also picked up by the
 * project's `pnpm test` glob over tests/js).
 */
const assert = require("node:assert");
const path = require("node:path");

const {
  bundleRelativePath,
  buildBundleFormData,
  collectHtmlCandidates,
  hasTopLevelIndexHtml,
} = require(path.join(__dirname, "../../static/editor/bundle-upload.js"));

function fileAt(relativePath, name) {
  const file = new File(["content"], name || relativePath.split("/").pop());
  file.webkitRelativePath = relativePath;
  return file;
}

// bundleRelativePath strips the leading folder segment picked via
// webkitdirectory ("my-site/index.html" -> "index.html").
(() => {
  assert.strictEqual(bundleRelativePath("my-site/index.html"), "index.html");
  assert.strictEqual(
    bundleRelativePath("my-site/assets/logo.png"),
    "assets/logo.png"
  );
})();

// bundleRelativePath falls back to the bare file name when there is no
// webkitRelativePath (single dropped file, unsupported browser).
(() => {
  assert.strictEqual(bundleRelativePath("", "index.html"), "index.html");
  assert.strictEqual(bundleRelativePath(undefined, "index.html"), "index.html");
})();

// buildBundleFormData sends "name" plus one field per file, keyed by the
// bundle-relative path — NEVER the raw webkitRelativePath (which would carry
// the folder name and break the backend's top-level index.html requirement).
(() => {
  const files = [
    fileAt("my-site/index.html"),
    fileAt("my-site/assets/logo.png"),
  ];
  const formData = buildBundleFormData("Mi sitio", files);
  assert.strictEqual(formData.get("name"), "Mi sitio");

  const keys = Array.from(formData.keys()).filter((key) => key !== "name");
  assert.deepStrictEqual(keys.sort(), ["assets/logo.png", "index.html"]);
  // Guard against the exact bug this contract exists to prevent.
  assert.ok(!keys.includes("my-site/index.html"));
  assert.ok(!keys.includes("my-site/assets/logo.png"));
})();

// buildBundleFormData defaults an empty/missing name to an empty string
// rather than throwing (the server applies its own fallback/truncation).
(() => {
  const formData = buildBundleFormData(undefined, [fileAt("site/index.html")]);
  assert.strictEqual(formData.get("name"), "");
})();

// buildBundleFormData only sends an "entrypoint" field when one is given —
// the common case (top-level index.html present) never sends it.
(() => {
  const withoutEntrypoint = buildBundleFormData("n", [fileAt("site/index.html")]);
  assert.strictEqual(withoutEntrypoint.get("entrypoint"), null);

  const withEntrypoint = buildBundleFormData(
    "n",
    [fileAt("site/home.html")],
    "home.html"
  );
  assert.strictEqual(withEntrypoint.get("entrypoint"), "home.html");
})();

// hasTopLevelIndexHtml / collectHtmlCandidates: the client pre-scan that
// decides whether to show the entrypoint picker before ever uploading (see
// design: "client pre-scan first, server 400 as the authoritative
// backstop").
(() => {
  const withIndex = [fileAt("site/index.html"), fileAt("site/assets/logo.png")];
  assert.strictEqual(hasTopLevelIndexHtml(withIndex), true);

  const withoutIndex = [
    fileAt("site/home.html"),
    fileAt("site/landing/start.html"),
    fileAt("site/assets/logo.png"),
  ];
  assert.strictEqual(hasTopLevelIndexHtml(withoutIndex), false);
  assert.deepStrictEqual(collectHtmlCandidates(withoutIndex), [
    "home.html",
    "landing/start.html",
  ]);

  // A nested index.html does NOT count as top-level.
  const nestedOnly = [fileAt("site/pages/index.html")];
  assert.strictEqual(hasTopLevelIndexHtml(nestedOnly), false);
  assert.deepStrictEqual(collectHtmlCandidates(nestedOnly), ["pages/index.html"]);
})();
