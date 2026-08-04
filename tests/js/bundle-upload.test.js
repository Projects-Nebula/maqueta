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

const { bundleRelativePath, buildBundleFormData } = require(
  path.join(__dirname, "../../static/editor/bundle-upload.js")
);

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
