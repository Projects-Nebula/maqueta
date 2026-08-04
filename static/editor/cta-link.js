/* Editor CTA link: double-clicking a button/anchor asks for a raw purchase
 * URL via native `window.prompt()` and applies it through the SAME
 * setAttribute(node, "href", value) primitive the inspector's `nodeHref`
 * field already uses (see editor-core.js) — no product picker, gateway
 * dropdown, or payment-link modal.
 *
 * Lives in its own file, mirroring bundle-upload.js, so this pure logic is
 * testable via `node --test` without touching editor-core.js's IIFE (see
 * CLAUDE.md: "do not clean up editor-core.js, it is the original editor IIFE
 * verbatim plus a facade"). Loaded BEFORE editor-core.js (unlike
 * bundle-upload.js) because editor-core.js's own dblclick handler calls into
 * it directly.
 */
(function (global) {
  "use strict";

  // Promotes a virtual <button> node to an <a> node in place: `href` is
  // inert on <button>, so linking a button requires it to become an anchor
  // first. Keeps attributes (classes, etc.) and children untouched; only the
  // tag changes and the now-meaningless `type` attribute is dropped.
  function promoteButtonToAnchor(node) {
    if (!node || node.tag !== "button") return node;
    node.tag = "a";
    if (node.attributes) delete node.attributes.type;
    return node;
  }

  // Resolves what `window.prompt()` returned into an action: `null` means
  // the seller cancelled the prompt (no-op); any string — including "" —
  // is a real value to apply (an empty string clears the href, matching
  // setAttribute's existing delete-on-falsy behavior).
  function resolvePromptedHref(promptResult) {
    if (promptResult === null) return { cancelled: true };
    return { cancelled: false, value: promptResult };
  }

  // --- Node export (tests) --------------------------------------------------
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { promoteButtonToAnchor, resolvePromptedHref };
    return;
  }

  global.EditorCtaLink = { promoteButtonToAnchor, resolvePromptedHref };
})(typeof window !== "undefined" ? window : globalThis);
