/* "Pegar HTML": paste external markup, get back a sanitized node, add it to
 * the end of the page. Lives in an external file because the page's CSP is
 * `script-src 'self'` — inline scripts are blocked. Runs after editor-core.js
 * so EditorCore exists.
 */
(function () {
  "use strict";

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  var button = document.getElementById("htmlImportButton");
  var modal = document.getElementById("htmlImportModal");
  var closeBtn = document.getElementById("htmlImportModalClose");
  var textarea = document.getElementById("htmlImportTextarea");
  var confirmBtn = document.getElementById("htmlImportConfirmBtn");
  if (!button || !modal || !window.EditorCore) return;

  function notify(message, tone) {
    if (window.EditorCore.showToast) window.EditorCore.showToast(message, tone || "error");
  }

  function openModal() {
    textarea.value = "";
    if (window.EditorModals) {
      window.EditorModals.open(modal, button);
    } else {
      modal.classList.remove("hidden");
    }
    textarea.focus();
  }

  function closeModal() {
    if (window.EditorModals) {
      window.EditorModals.closeAll();
    } else {
      modal.classList.add("hidden");
    }
  }

  async function importHtml() {
    var html = textarea.value.trim();
    if (!html) return;
    confirmBtn.disabled = true;
    try {
      var response = await fetch("/api/ai/editor/import-html/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ html: html }),
      });
      var data = await response.json();
      if (!response.ok) {
        notify(data.detail || "No se pudo importar el HTML.");
        return;
      }
      var state = window.EditorCore.getState();
      state.document.body.children.push(data.node);
      window.EditorCore.commitProposal(state);
      closeModal();
      var message = "HTML importado.";
      if (data.skipped_attributes) {
        message += " " + data.skipped_attributes + " atributo(s)/estilo(s) no se conservaron.";
      }
      notify(message, "success");
    } catch (e) {
      notify("No se pudo importar el HTML.");
    } finally {
      confirmBtn.disabled = false;
    }
  }

  button.addEventListener("click", openModal);
  closeBtn.addEventListener("click", closeModal);
  confirmBtn.addEventListener("click", importHtml);
})();
