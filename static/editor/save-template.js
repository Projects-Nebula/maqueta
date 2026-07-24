/* Saves the current editor state as a UserTemplate via the API.
 *
 * Lives in an external file because the page's CSP is `script-src 'self'` —
 * inline scripts are blocked. Runs after editor-core.js so EditorCore exists.
 *
 * "Actualizar" (PATCH) is only offered when the editor was opened from an
 * owned UserTemplate (?ut=<id>, see editor_view); base templates (?t=<slug>)
 * and a fresh/no-template session only ever get "Crear nuevo" (POST).
 */
(function () {
  "use strict";

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  var saveButton = document.getElementById("saveTemplateButton");
  var modal = document.getElementById("saveTemplateModal");
  var backdrop = document.getElementById("editorModalBackdrop");
  var closeBtn = document.getElementById("saveTemplateModalClose");
  var updateBtn = document.getElementById("saveTemplateUpdateBtn");
  var createBtn = document.getElementById("saveTemplateCreateBtn");
  var nameInput = document.getElementById("saveTemplateNameInput");
  var historyToggle = document.getElementById("saveTemplateHistoryToggle");
  var historyList = document.getElementById("saveTemplateHistoryList");
  var publishBtn = document.getElementById("saveTemplatePublishBtn");
  var unpublishBtn = document.getElementById("saveTemplateUnpublishBtn");
  var publicUrlEl = document.getElementById("saveTemplatePublicUrl");
  if (!saveButton || !modal || !window.EditorCore) return;

  var userTemplateId = document.body.dataset.userTemplateId || "";
  var historyOpen = false;

  function notify(message, tone) {
    if (window.EditorCore && window.EditorCore.showToast) {
      window.EditorCore.showToast(message, tone || "error");
    } else {
      var fallback = document.getElementById("toast");
      if (fallback) {
        fallback.textContent = message;
        fallback.dataset.tone = tone || "error";
        fallback.classList.add("visible");
      }
    }
  }

  function closeModal() {
    if (window.EditorModals) {
      window.EditorModals.closeAll();
      return;
    }
    modal.classList.add("hidden");
    if (backdrop) backdrop.classList.add("hidden");
  }

  function renderPublishState(data) {
    var isPublished = !!(data && data.is_published);
    publishBtn.classList.toggle("hidden", isPublished);
    unpublishBtn.classList.toggle("hidden", !isPublished);
    if (isPublished && data.public_slug) {
      var url = window.location.origin + "/t/" + data.public_slug + "/";
      publicUrlEl.textContent = "Publicado: ";
      var link = document.createElement("a");
      link.href = url;
      link.textContent = url;
      link.target = "_blank";
      link.rel = "noopener";
      publicUrlEl.appendChild(link);
      publicUrlEl.classList.remove("hidden");
    } else {
      publicUrlEl.classList.add("hidden");
      publicUrlEl.textContent = "";
    }
  }

  async function loadPublishState() {
    try {
      var response = await fetch("/api/user-templates/" + encodeURIComponent(userTemplateId) + "/", {
        credentials: "same-origin",
      });
      if (response.ok) renderPublishState(await response.json());
    } catch (e) {
      /* ponytail: publish-state fetch is best-effort, the buttons just stay at their default state */
    }
  }

  async function togglePublish(action) {
    try {
      var response = await fetch(
        "/api/user-templates/" + encodeURIComponent(userTemplateId) + "/" + action + "/",
        { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": getCsrfToken() } }
      );
      if (!response.ok) {
        notify("No se pudo actualizar el estado de publicación.");
        return;
      }
      renderPublishState(await response.json());
    } catch (e) {
      notify("No se pudo actualizar el estado de publicación.");
    }
  }

  function openModal() {
    var hasUserTemplate = !!userTemplateId;
    updateBtn.classList.toggle("hidden", !hasUserTemplate);
    historyToggle.classList.toggle("hidden", !hasUserTemplate);
    historyOpen = false;
    historyList.classList.add("hidden");
    historyList.innerHTML = "";
    nameInput.value = "";
    if (window.EditorModals) {
      window.EditorModals.open(modal, saveButton);
    } else {
      modal.classList.remove("hidden");
      if (backdrop) backdrop.classList.remove("hidden");
    }
    nameInput.focus();
  }

  function renderHistory(revisions) {
    historyList.innerHTML = "";
    if (!revisions.length) {
      historyList.textContent = "Todavía no hay versiones anteriores.";
      return;
    }
    revisions.forEach(function (rev) {
      var row = document.createElement("div");
      row.className = "ai-history-row";
      var label = document.createElement("span");
      label.textContent = "v" + rev.version + " · " + new Date(rev.created_at).toLocaleString("es");

      var actions = document.createElement("div");
      actions.className = "ai-history-actions";

      var restoreBtn = document.createElement("button");
      restoreBtn.type = "button";
      restoreBtn.className = "btn small";
      restoreBtn.textContent = "Restaurar";
      restoreBtn.addEventListener("click", function () {
        restoreRevision(rev);
      });

      var deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "btn small danger";
      deleteBtn.textContent = "Eliminar";
      deleteBtn.addEventListener("click", function () {
        deleteRevision(rev);
      });

      actions.appendChild(restoreBtn);
      actions.appendChild(deleteBtn);
      row.appendChild(label);
      row.appendChild(actions);
      historyList.appendChild(row);
    });
  }

  async function deleteRevision(rev) {
    if (!confirm("¿Eliminar la versión v" + rev.version + "? No se puede deshacer.")) return;
    try {
      var response = await fetch(
        "/api/user-templates/" +
          encodeURIComponent(userTemplateId) +
          "/revisions/" +
          encodeURIComponent(rev.id) +
          "/",
        {
          method: "DELETE",
          credentials: "same-origin",
          headers: { "X-CSRFToken": getCsrfToken() },
        }
      );
      if (!response.ok) {
        notify("No se pudo eliminar la versión.");
        return;
      }
      loadHistory();
    } catch (e) {
      notify("No se pudo eliminar la versión.");
    }
  }

  async function loadHistory() {
    historyList.classList.remove("hidden");
    historyList.textContent = "Cargando…";
    try {
      var response = await fetch(
        "/api/user-templates/" + encodeURIComponent(userTemplateId) + "/revisions/",
        { credentials: "same-origin" }
      );
      if (!response.ok) {
        historyList.textContent = "No se pudo cargar el historial.";
        return;
      }
      renderHistory(await response.json());
    } catch (e) {
      historyList.textContent = "No se pudo cargar el historial.";
    }
  }

  async function restoreRevision(rev) {
    try {
      var response = await fetch("/api/user-templates/" + encodeURIComponent(userTemplateId) + "/", {
        method: "PATCH",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ state: rev.state }),
      });
      if (!response.ok) {
        notify("No se pudo restaurar la versión.");
        return;
      }
      window.EditorCore.commitProposal(rev.state);
      closeModal();
      notify("Versión v" + rev.version + " restaurada.", "success");
    } catch (e) {
      notify("No se pudo restaurar la versión.");
    }
  }

  publishBtn.addEventListener("click", function () {
    togglePublish("publish");
  });
  unpublishBtn.addEventListener("click", function () {
    togglePublish("unpublish");
  });

  historyToggle.addEventListener("click", function () {
    historyOpen = !historyOpen;
    if (historyOpen) {
      loadHistory();
    } else {
      historyList.classList.add("hidden");
    }
  });

  async function submit(url, method, body, button) {
    if (button) {
      button.disabled = true;
      button.dataset.originalLabel = button.textContent;
      button.textContent = "Guardando…";
    }
    try {
      var response = await fetch(url, {
        method: method,
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(body),
      });
      if (response.ok) {
        window.location.href = "/gallery/";
      } else {
        notify("No se pudo guardar el template.");
      }
    } catch (e) {
      notify("No se pudo guardar el template.");
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = button.dataset.originalLabel || button.textContent;
      }
    }
  }

  saveButton.addEventListener("click", openModal);
  closeBtn.addEventListener("click", closeModal);

  updateBtn.addEventListener("click", function () {
    if (!userTemplateId) return;
    submit("/api/user-templates/" + encodeURIComponent(userTemplateId) + "/", "PATCH", {
      state: window.EditorCore.getState(),
    }, updateBtn);
  });

  createBtn.addEventListener("click", function () {
    var name = nameInput.value.trim();
    if (!name) {
      nameInput.focus();
      return;
    }
    submit("/api/user-templates/", "POST", { name: name, state: window.EditorCore.getState() }, createBtn);
  });

  // Publish/unpublish live as their own topbar buttons (not inside the
  // save modal) — same precondition as Actualizar/Historial (needs a
  // saved UserTemplate id) but visible without opening anything first.
  // Both buttons start hidden in the template; renderPublishState (called
  // by loadPublishState below) reveals whichever one actually applies.
  if (userTemplateId) loadPublishState();
})();
