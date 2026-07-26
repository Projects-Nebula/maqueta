/* Ctrl/Cmd+K command palette: filtered list of editor actions, dispatching
 * to the existing buttons (topbar + quick-insert presets) rather than
 * duplicating their logic. The overlay is still built entirely in JS (no
 * template markup needed) — lives in an external file because the page's
 * CSP is `script-src 'self'` — but registers itself with the shared
 * EditorModals system (editor-ai.js) instead of hand-rolling open/close, so
 * it gets the same Tab-trapping, Escape handling, and focus-restore-to-
 * trigger every other editor dialog already has.
 *
 * Quick-insert presets ([data-preset]) dispatch fine even while
 * #sectionModal is closed: .click() fires their listener regardless of
 * visibility, and the handler (editor-core.js) only touches state + CSS
 * classes on elements that already exist in the DOM — verified before
 * widening the palette to include them (see PLAN.md step 4).
 */
(function () {
  "use strict";

  if (!window.EditorCore || !window.EditorModals) return;

  var COMMANDS = [
    { label: "Guardar", id: "saveTemplateButton" },
    { label: "Deshacer", id: "undoButton" },
    { label: "Rehacer", id: "redoButton" },
    { label: "Pegar HTML", id: "htmlImportButton" },
    { label: "Importar JSON", id: "importButton" },
    { label: "Descargar JSON", id: "downloadButton" },
    { label: "Copiar JSON", id: "copyButton" },
    { label: "Insertar sección: Hero", selector: '[data-preset="hero"]' },
    { label: "Insertar sección: Beneficios", selector: '[data-preset="features"]' },
    { label: "Insertar sección: Texto", selector: '[data-preset="text"]' },
    { label: "Insertar sección: Imagen", selector: '[data-preset="image"]' },
    { label: "Insertar sección: Llamado a la acción", selector: '[data-preset="cta"]' },
    { label: "Insertar sección: Footer", selector: '[data-preset="footer"]' },
  ];

  var overlay = null;
  var input = null;
  var list = null;

  function buildOverlay() {
    overlay = document.createElement("div");
    overlay.id = "commandPaletteOverlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Paleta de comandos");
    overlay.setAttribute("aria-hidden", "true");
    overlay.className = "hidden";
    // No own backdrop/background: the shared #editorModalBackdrop (already
    // shown/hidden by EditorModals.open/closeAll) handles page dimming.
    // z-index above the backdrop's 1000, matching every other .panel-modal.
    overlay.style.cssText =
      "position:fixed;inset:0;z-index:1001;" +
      "display:flex;align-items:flex-start;justify-content:center;padding-top:15vh;";

    var box = document.createElement("div");
    box.style.cssText =
      "background:var(--panel-bg,#fff);color:var(--text,#111);" +
      "border-radius:var(--radius,10px);box-shadow:var(--shadow,0 10px 30px rgba(0,0,0,.2));" +
      "width:min(480px,90vw);overflow:hidden;";

    input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Buscar un comando…";
    input.style.cssText =
      "width:100%;box-sizing:border-box;padding:12px 16px;border:0;outline:none;" +
      "font:inherit;background:transparent;color:inherit;border-bottom:1px solid var(--border,#ddd);";

    list = document.createElement("div");
    list.style.cssText = "max-height:50vh;overflow:auto;";

    box.appendChild(input);
    box.appendChild(list);
    overlay.appendChild(box);
    // Click on the transparent margin around the box (not the shared
    // backdrop element itself, which already closes on click) also closes.
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) window.EditorModals.closeAll();
    });
    document.body.appendChild(overlay);
    window.EditorModals.register(overlay);

    input.addEventListener("input", function () {
      render(input.value);
    });
    // Escape/Tab are already handled globally by EditorModals once this
    // overlay is the active modal — no local keydown handling needed here.
  }

  function render(filter) {
    list.innerHTML = "";
    var query = (filter || "").toLowerCase();
    var matches = COMMANDS.filter(function (cmd) {
      return cmd.label.toLowerCase().indexOf(query) !== -1;
    });
    matches.forEach(function (cmd) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = cmd.label;
      btn.style.cssText =
        "display:block;width:100%;text-align:left;padding:10px 16px;border:0;" +
        "background:transparent;color:inherit;cursor:pointer;font:inherit;";
      btn.addEventListener("mouseenter", function () {
        btn.style.background = "var(--panel-soft,#f3f3f3)";
      });
      btn.addEventListener("mouseleave", function () {
        btn.style.background = "transparent";
      });
      btn.addEventListener("click", function () {
        run(cmd);
      });
      list.appendChild(btn);
    });
    if (!matches.length) {
      var empty = document.createElement("div");
      empty.style.cssText = "padding:10px 16px;color:var(--muted,#888);";
      empty.textContent = "Sin resultados.";
      list.appendChild(empty);
    }
  }

  function run(cmd) {
    window.EditorModals.closeAll();
    var el = cmd.id ? document.getElementById(cmd.id) : document.querySelector(cmd.selector);
    if (el) el.click();
  }

  function open() {
    if (!overlay) buildOverlay();
    window.EditorModals.open(overlay);
    input.value = "";
    render("");
    input.focus();
  }

  document.addEventListener("keydown", function (e) {
    if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (overlay && window.EditorModals.getActive() === overlay) {
        window.EditorModals.closeAll();
      } else {
        open();
      }
    }
  });
})();
