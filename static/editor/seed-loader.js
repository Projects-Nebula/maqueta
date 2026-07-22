/* Applies the server-injected template seed.
 *
 * editor_view injects the chosen template's state as a #template-seed
 * <script type="application/json"> (json_script). This runs after EditorCore is
 * defined and swaps the default page for that state. Lives in an external file
 * because the page's CSP is `script-src 'self'` — inline scripts are blocked.
 * A null seed (built-in default or unknown slug) is ignored.
 */
(function () {
  "use strict";
  var el = document.getElementById("template-seed");
  if (!el) return;
  var state = null;
  try {
    state = JSON.parse(el.textContent);
  } catch (e) {
    return;
  }
  if (state && window.EditorCore && typeof window.EditorCore.loadSeed === "function") {
    window.EditorCore.loadSeed(state);
  }
})();
