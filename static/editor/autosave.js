/* Autosaves the editor state as a Project revision while editing a project
 * (?p=<id>, see editor_view). No-ops entirely for templates/user-templates,
 * which have their own explicit "Guardar" flow (save-template.js).
 *
 * Lives in an external file because the page's CSP is `script-src 'self'` —
 * inline scripts are blocked. Runs after editor-core.js so EditorCore exists.
 */
(function () {
  "use strict";

  var AUTOSAVE_DEBOUNCE_MS = 3000;

  var projectId = document.body.dataset.projectId || "";
  if (!projectId || !window.EditorCore) return;

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  var timer = null;
  var saving = false;
  var pendingResave = false;

  function save() {
    if (saving) {
      pendingResave = true;
      return;
    }
    saving = true;
    fetch("/api/projects/" + encodeURIComponent(projectId) + "/revisions/", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ state: window.EditorCore.getState(), source: "manual" }),
    })
      .catch(function () {
        // ponytail: silent best-effort autosave, no retry/backoff — add one
        // if data loss from a failed autosave ever becomes a real complaint.
      })
      .finally(function () {
        saving = false;
        if (pendingResave) {
          pendingResave = false;
          save();
        }
      });
  }

  document.addEventListener("vjpb:state-committed", function () {
    clearTimeout(timer);
    timer = setTimeout(save, AUTOSAVE_DEBOUNCE_MS);
  });
})();
