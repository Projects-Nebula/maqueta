/* Unit tests for the editor's CTA link helpers (replaces the old
 * `openPaymentLinkModal` product-picker flow). Highest-risk piece of PR1:
 * `<button>` never navigates on `href`, so linking a button requires
 * promoting it to `<a>` first — get that wrong and the CTA silently does
 * nothing when published. `resolvePromptedHref` keeps the
 * cancel-vs-clear-vs-set decision (native `window.prompt()` returns `null`
 * on cancel, `""` when the seller clears the field) out of the DOM-wiring
 * code so it is testable without a browser.
 *
 * Run with `node tests/js/cta-link.test.js` (also picked up by the
 * project's `pnpm test` glob over tests/js).
 */
const assert = require("node:assert");
const path = require("node:path");

const { promoteButtonToAnchor, resolvePromptedHref } = require(
  path.join(__dirname, "../../static/editor/cta-link.js")
);

// promoteButtonToAnchor turns a virtual <button> node into an <a> node,
// dropping the now-meaningless "type" attribute while keeping everything
// else (classes, other attributes, children) untouched.
(() => {
  const node = {
    type: "element",
    tag: "button",
    attributes: { class: ["btn", "primary"], type: "submit" },
    children: [{ type: "text", value: "Comprar" }],
  };
  const result = promoteButtonToAnchor(node);
  assert.strictEqual(result, node, "mutates and returns the same node");
  assert.strictEqual(node.tag, "a");
  assert.deepStrictEqual(node.attributes.class, ["btn", "primary"]);
  assert.strictEqual("type" in node.attributes, false);
  assert.deepStrictEqual(node.children, [{ type: "text", value: "Comprar" }]);
})();

// promoteButtonToAnchor is a no-op for nodes that are already an anchor (or
// any other tag) — never touches non-button nodes.
(() => {
  const node = { type: "element", tag: "a", attributes: { href: "/x" }, children: [] };
  const result = promoteButtonToAnchor(node);
  assert.strictEqual(result, node);
  assert.strictEqual(node.tag, "a");
  assert.deepStrictEqual(node.attributes, { href: "/x" });
})();

// promoteButtonToAnchor tolerates a button with no attributes object at all.
(() => {
  const node = { type: "element", tag: "button", children: [] };
  promoteButtonToAnchor(node);
  assert.strictEqual(node.tag, "a");
})();

// resolvePromptedHref: `null` (prompt cancelled) is a no-op.
(() => {
  const resolved = resolvePromptedHref(null);
  assert.strictEqual(resolved.cancelled, true);
})();

// resolvePromptedHref: empty string is a real, non-cancelled value (clears
// the href via the same setAttribute(node,"href",value) primitive that
// deletes the attribute on falsy input).
(() => {
  const resolved = resolvePromptedHref("");
  assert.strictEqual(resolved.cancelled, false);
  assert.strictEqual(resolved.value, "");
})();

// resolvePromptedHref: a real URL is passed through unchanged.
(() => {
  const resolved = resolvePromptedHref("https://pay.example.com/checkout/1");
  assert.strictEqual(resolved.cancelled, false);
  assert.strictEqual(resolved.value, "https://pay.example.com/checkout/1");
})();
