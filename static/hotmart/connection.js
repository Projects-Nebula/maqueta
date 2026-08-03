/* Hotmart connection page shell — paste-credential form (POST
 * /api/hotmart/credentials/) plus disconnect button. Mirrors the
 * password-masking pattern in static/storefront/payment-config.js:
 * type=password inputs, autocomplete=off, values never echoed back, blank
 * fields mean "keep the existing stored value" (server-side merge).
 *
 * Also renders the connected seller's product catalog (GET
 * /api/hotmart/products/) and drives the "Generar landing" flow: a fixed
 * 3-question form + optional checkout link, POSTed as SSE to
 * /api/hotmart/products/<id>/generate/ and consumed via the same
 * window.AIStream.consume transport the editor's AI wizard uses (see
 * static/editor/template-wizard.js).
 */
(function () {
  "use strict";

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function feedback(message, tone) {
    if (window.AppFeedback) window.AppFeedback.show(message, { tone: tone || "info" });
  }

  var disconnectBtn = document.getElementById("disconnectBtn");
  if (disconnectBtn) {
    disconnectBtn.addEventListener("click", async function () {
      if (!window.confirm("¿Desconectar tu cuenta de Hotmart?")) return;
      disconnectBtn.disabled = true;
      try {
        var response = await fetch("/api/hotmart/disconnect/", {
          method: "POST",
          headers: { "X-CSRFToken": getCsrfToken() },
        });
        if (!response.ok) throw new Error("disconnect failed");
        window.location.reload();
      } catch (err) {
        feedback("No se pudo desconectar la cuenta de Hotmart.", "error");
        disconnectBtn.disabled = false;
      }
    });
  }

  var credentialsForm = document.getElementById("credentialsForm");
  if (!credentialsForm) return;

  var clientIdInput = document.getElementById("clientIdInput");
  var clientSecretInput = document.getElementById("clientSecretInput");
  var saveCredentialsBtn = document.getElementById("saveCredentialsBtn");

  credentialsForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    var connected = credentialsForm.dataset.connected === "true";
    var clientId = clientIdInput.value.trim();
    var clientSecret = clientSecretInput.value.trim();

    if (!connected && (!clientId || !clientSecret)) {
      feedback("Completá el Client ID y el Client Secret.", "error");
      return;
    }

    var originalLabel = saveCredentialsBtn.textContent;
    saveCredentialsBtn.disabled = true;
    saveCredentialsBtn.textContent = "Guardando…";
    try {
      var response = await fetch("/api/hotmart/credentials/", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
        body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
      });
      if (!response.ok) {
        var data = await response.json().catch(function () { return {}; });
        if (data.error === "invalid_credentials") {
          throw new Error("Hotmart rechazó esas credenciales. Revisá el Client ID y el Client Secret.");
        }
        var detail = data.detail || data.error || data.message;
        throw new Error(detail ? "No se pudieron guardar las credenciales. " + detail : "No se pudieron guardar las credenciales.");
      }
      feedback("Cuenta de Hotmart conectada.", "success");
      window.location.reload();
    } catch (error) {
      feedback(error.message || "No se pudieron guardar las credenciales.", "error");
      saveCredentialsBtn.disabled = false;
      saveCredentialsBtn.textContent = originalLabel;
    }
  });

  // --- Product list + "Generar landing" flow -------------------------------

  var productListEl = document.getElementById("productList");
  if (!productListEl) return;

  var modalBackdrop = document.getElementById("landingModalBackdrop");
  var landingForm = document.getElementById("landingGenerateForm");
  var audienceInput = document.getElementById("landingAudience");
  var promiseInput = document.getElementById("landingPromise");
  var offerDetailsInput = document.getElementById("landingOfferDetails");
  var checkoutUrlInput = document.getElementById("landingCheckoutUrl");
  var progressEl = document.getElementById("landingProgress");
  var submitBtn = document.getElementById("landingSubmitBtn");
  var cancelBtn = document.getElementById("landingCancelBtn");

  var activeProductId = null;

  var errorMessages = {
    product_not_active: "Este producto no está activo en Hotmart todavía.",
    product_not_found: "No encontramos ese producto en tu catálogo de Hotmart.",
    reconnect_required: "Tu conexión con Hotmart venció. Reconectá tu cuenta.",
    upstream_unavailable: "Hotmart no respondió. Intentá de nuevo en un momento.",
    ai_timeout: "El asistente tardó demasiado. Intentá de nuevo.",
    ai_unavailable: "El asistente no está disponible ahora.",
    invalid_document: "No se pudo generar la página. Intentá de nuevo.",
    invalid_input: "Revisá los datos del formulario.",
    network_error: "No se pudo conectar. Revisá tu conexión e intentá de nuevo.",
  };

  function errorMessage(code) {
    return errorMessages[code] || "Algo salió mal. Intentá de nuevo.";
  }

  function renderProducts(products) {
    productListEl.innerHTML = "";
    if (!products.length) {
      var empty = document.createElement("p");
      empty.textContent = "Todavía no tenés productos en tu cuenta de Hotmart.";
      productListEl.appendChild(empty);
      return;
    }
    products.forEach(function (product) {
      var card = document.createElement("div");
      card.className = "product-card";

      var info = document.createElement("div");
      var name = document.createElement("span");
      name.className = "product-name";
      name.textContent = product.name || product.id;
      info.appendChild(name);
      var status = document.createElement("span");
      status.className = "product-status" + (product.is_active ? "" : " inactive");
      status.textContent = product.is_active ? "Activo" : "No activo en Hotmart";
      info.appendChild(status);
      card.appendChild(info);

      var button = document.createElement("button");
      button.type = "button";
      button.className = "btn primary small";
      button.textContent = product.linked ? "Regenerar landing" : "Generar landing";
      button.disabled = !product.is_active;
      button.addEventListener("click", function () {
        openLandingModal(product.id);
      });
      card.appendChild(button);

      productListEl.appendChild(card);
    });
  }

  async function loadProducts() {
    try {
      var response = await fetch("/api/hotmart/products/", { credentials: "same-origin" });
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok || !data.connected) return;
      renderProducts(data.products || []);
    } catch (err) {
      feedback("No se pudieron cargar tus productos de Hotmart.", "error");
    }
  }

  function openLandingModal(productId) {
    activeProductId = productId;
    landingForm.reset();
    progressEl.textContent = "";
    submitBtn.disabled = false;
    submitBtn.textContent = "Generar landing";
    modalBackdrop.classList.remove("hidden");
    audienceInput.focus();
  }

  function closeLandingModal() {
    modalBackdrop.classList.add("hidden");
    activeProductId = null;
  }

  cancelBtn.addEventListener("click", closeLandingModal);
  modalBackdrop.addEventListener("click", function (event) {
    if (event.target === modalBackdrop) closeLandingModal();
  });

  landingForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (!activeProductId) return;
    if (!landingForm.reportValidity()) return;

    var body = {
      answers: {
        audience: audienceInput.value.trim(),
        promise: promiseInput.value.trim(),
        offer_details: offerDetailsInput.value.trim(),
      },
      checkout_url: checkoutUrlInput.value.trim(),
    };

    submitBtn.disabled = true;
    submitBtn.textContent = "Generando…";
    progressEl.textContent = "El asistente está trabajando…";

    try {
      var response = await fetch(
        "/api/hotmart/products/" + encodeURIComponent(activeProductId) + "/generate/",
        {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
          body: JSON.stringify(body),
        },
      );
      var contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("text/event-stream")) {
        var errorData = await response.json().catch(function () { return {}; });
        throw new Error(errorMessage(errorData.error));
      }
      var result = await window.AIStream.consume(response, function (text) {
        progressEl.textContent = text.slice(-160);
      });
      if (result.error) throw new Error(errorMessage(result.error.error));
      if (!result.done) throw new Error(errorMessage());

      closeLandingModal();
      feedback("¡Landing generada! Abriendo el editor…", "success");
      window.location.href = result.done.editor_url;
    } catch (err) {
      progressEl.textContent = "";
      submitBtn.disabled = false;
      submitBtn.textContent = "Generar landing";
      // TypeError here means fetch() itself failed (offline, DNS, CORS) —
      // err.message is an untranslated browser string like "Failed to
      // fetch". Every other throw in this handler already wraps a
      // translated errorMessage(), so err.message is safe to use as-is.
      var message = err instanceof TypeError ? errorMessage("network_error") : err.message;
      feedback(message || "No se pudo generar la landing.", "error");
    }
  });

  loadProducts();
})();
