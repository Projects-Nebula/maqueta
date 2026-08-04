/* "Subir sitio": pick a local folder (HTML + assets), upload it as a
 * SiteBundle, then offer the two post-upload actions ("Publicar tal cual" /
 * "Editar antes de publicar"). Lives in an external file because the page's
 * CSP is `script-src 'self'` — inline scripts are blocked. Runs after
 * editor-core.js so EditorCore exists (only used for showToast here; this
 * feature never touches document state).
 *
 * Upload multipart contract (see apps/editor/views.py::BundleViewSet.create):
 * every multipart field whose key is NOT "name"/"entrypoint" is treated as
 * one file, keyed by its bundle-relative path (e.g. a field literally named
 * "assets/logo.png"). `File.webkitRelativePath` includes the picked folder's
 * OWN name as its first path segment (e.g. "my-site/index.html"), which is
 * NOT bundle-relative — it must be stripped before use as a field name, or
 * the backend never sees a top-level "index.html" and every upload 400s with
 * missing_entrypoint. bundleRelativePath/buildBundleFormData/
 * collectHtmlCandidates/hasTopLevelIndexHtml below are pure and exported for
 * Node tests (see tests/js/bundle-upload.test.js); the DOM wiring after them
 * only runs in the browser.
 *
 * Entrypoint selection (design: "client pre-scan first, server 400 as the
 * authoritative backstop"): if the picked folder has no top-level
 * "index.html", the picker is shown BEFORE uploading so the seller always
 * sends an explicit `entrypoint` field. The server's `400
 * entrypoint_required {candidates:[...]}` response remains the mandatory,
 * fully-implemented backstop (e.g. the pre-scan and the server can
 * disagree if the folder changed between scan and upload) — its
 * `candidates` list, not just the client scan, populates the picker.
 */
(function (global) {
  "use strict";

  // "my-site/assets/logo.png" -> "assets/logo.png". Falls back to the bare
  // file name when there is no webkitRelativePath (browsers without
  // directory-picker support, or a single dropped file).
  function bundleRelativePath(webkitRelativePath, fallbackName) {
    if (!webkitRelativePath) return fallbackName || "";
    const slash = webkitRelativePath.indexOf("/");
    return slash === -1 ? webkitRelativePath : webkitRelativePath.slice(slash + 1);
  }

  function isHtmlPath(path) {
    return /\.html?$/i.test(path);
  }

  // Sorted list of every .html/.htm bundle-relative path in `files` — used
  // to populate the entrypoint picker before the server is ever asked.
  function collectHtmlCandidates(files) {
    var candidates = [];
    Array.prototype.forEach.call(files, function (file) {
      var path = bundleRelativePath(file.webkitRelativePath, file.name);
      if (path && isHtmlPath(path)) candidates.push(path);
    });
    candidates.sort();
    return candidates;
  }

  function hasTopLevelIndexHtml(files) {
    return collectHtmlCandidates(files).indexOf("index.html") !== -1;
  }

  // Builds the FormData for POST /api/editor/bundles/ from a FileList/array
  // of File objects picked via a `webkitdirectory` input. "name" is a fixed
  // key, "entrypoint" is an optional fixed key (only sent when the seller
  // had to pick one — see module docstring); every other field key IS
  // itself a bundle-relative path.
  function buildBundleFormData(name, files, entrypoint) {
    const formData = new global.FormData();
    formData.append("name", name || "");
    if (entrypoint) formData.append("entrypoint", entrypoint);
    Array.prototype.forEach.call(files, function (file) {
      const path = bundleRelativePath(file.webkitRelativePath, file.name);
      if (path) formData.append(path, file);
    });
    return formData;
  }

  // --- Node export (tests) --------------------------------------------------
  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      bundleRelativePath,
      buildBundleFormData,
      collectHtmlCandidates,
      hasTopLevelIndexHtml,
    };
    return;
  }

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  var button = document.getElementById("bundleUploadButton");
  var modal = document.getElementById("bundleUploadModal");
  var closeBtn = document.getElementById("bundleUploadModalClose");
  var nameInput = document.getElementById("bundleUploadNameInput");
  var browseBtn = document.getElementById("bundleUploadBrowseBtn");
  var fileInput = document.getElementById("bundleUploadInput");
  var statusEl = document.getElementById("bundleUploadStatus");
  var stepSelect = document.getElementById("bundleUploadStepSelect");
  var stepEntrypoint = document.getElementById("bundleUploadStepEntrypoint");
  var entrypointSelect = document.getElementById("bundleUploadEntrypointSelect");
  var entrypointConfirmBtn = document.getElementById("bundleUploadEntrypointConfirmBtn");
  var stepResult = document.getElementById("bundleUploadStepResult");
  var targetSelect = document.getElementById("bundleUploadTargetSelect");
  var deployBtn = document.getElementById("bundleUploadDeployBtn");
  var convertBtn = document.getElementById("bundleUploadConvertBtn");
  var resultMessage = document.getElementById("bundleUploadResultMessage");
  if (!button || !modal || !window.EditorCore) return;

  var currentBundleId = null;
  var pendingFiles = null;

  function notify(message, tone) {
    if (window.EditorCore.showToast) window.EditorCore.showToast(message, tone || "error");
  }

  function resetModal() {
    nameInput.value = "";
    fileInput.value = "";
    statusEl.textContent = "";
    resultMessage.textContent = "";
    currentBundleId = null;
    pendingFiles = null;
    stepSelect.classList.remove("hidden");
    stepEntrypoint.classList.add("hidden");
    stepResult.classList.add("hidden");
    if (targetSelect) targetSelect.value = "vercel";
  }

  function openModal() {
    resetModal();
    if (window.EditorModals) {
      window.EditorModals.open(modal, button);
    } else {
      modal.classList.remove("hidden");
    }
  }

  function closeModal() {
    if (window.EditorModals) {
      window.EditorModals.closeAll();
    } else {
      modal.classList.add("hidden");
    }
  }

  function showEntrypointPicker(candidates) {
    entrypointSelect.innerHTML = "";
    candidates.forEach(function (path) {
      var option = document.createElement("option");
      option.value = path;
      option.textContent = path;
      entrypointSelect.appendChild(option);
    });
    stepSelect.classList.add("hidden");
    stepEntrypoint.classList.remove("hidden");
  }

  async function submitBundle(entrypoint) {
    statusEl.textContent = "Subiendo…";
    browseBtn.disabled = true;
    entrypointConfirmBtn.disabled = true;
    try {
      var formData = buildBundleFormData(nameInput.value.trim(), pendingFiles, entrypoint);
      var response = await fetch("/api/editor/bundles/", {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": getCsrfToken() },
        body: formData,
      });
      var data = await response.json();
      if (!response.ok) {
        if (data.error === "entrypoint_required" && data.candidates) {
          showEntrypointPicker(data.candidates);
          return;
        }
        notify(data.detail || "No se pudo subir el sitio.");
        return;
      }
      currentBundleId = data.id;
      stepSelect.classList.add("hidden");
      stepEntrypoint.classList.add("hidden");
      stepResult.classList.remove("hidden");
    } catch (e) {
      notify("No se pudo subir el sitio.");
    } finally {
      statusEl.textContent = "";
      browseBtn.disabled = false;
      entrypointConfirmBtn.disabled = false;
    }
  }

  function uploadBundle() {
    var files = fileInput.files;
    if (!files || files.length === 0) {
      notify("Elegí una carpeta con tu sitio.");
      return;
    }
    pendingFiles = files;
    if (!hasTopLevelIndexHtml(files)) {
      showEntrypointPicker(collectHtmlCandidates(files));
      return;
    }
    submitBundle();
  }

  function confirmEntrypoint() {
    if (!pendingFiles || !entrypointSelect.value) return;
    submitBundle(entrypointSelect.value);
  }

  async function deployBundle() {
    if (!currentBundleId) return;
    deployBtn.disabled = true;
    try {
      var target = targetSelect ? targetSelect.value : "vercel";
      var response = await fetch("/api/editor/bundles/" + currentBundleId + "/deploy/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "X-CSRFToken": getCsrfToken(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ target: target }),
      });
      var data = await response.json();
      if (!response.ok) {
        notify(
          data.error === "vercel_requires_index"
            ? "Este sitio no tiene index.html: solo se puede alojar en maqueta."
            : "No se pudo publicar el sitio."
        );
        return;
      }
      resultMessage.textContent = "Publicado en " + data.url;
      notify("Sitio publicado.", "success");
    } catch (e) {
      notify("No se pudo publicar el sitio.");
    } finally {
      deployBtn.disabled = false;
    }
  }

  async function convertBundle() {
    if (!currentBundleId) return;
    convertBtn.disabled = true;
    try {
      var response = await fetch("/api/editor/bundles/" + currentBundleId + "/convert/", {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": getCsrfToken() },
      });
      if (response.status === 501) {
        resultMessage.textContent = "Editar antes de publicar todavía no está disponible.";
        notify("Esta acción todavía no está disponible.");
        return;
      }
      if (!response.ok) {
        notify("No se pudo procesar la solicitud.");
      }
    } catch (e) {
      notify("No se pudo procesar la solicitud.");
    } finally {
      convertBtn.disabled = false;
    }
  }

  button.addEventListener("click", openModal);
  closeBtn.addEventListener("click", closeModal);
  browseBtn.addEventListener("click", function () {
    fileInput.click();
  });
  fileInput.addEventListener("change", uploadBundle);
  entrypointConfirmBtn.addEventListener("click", confirmEntrypoint);
  deployBtn.addEventListener("click", deployBundle);
  convertBtn.addEventListener("click", convertBundle);
})(typeof window !== "undefined" ? window : globalThis);
