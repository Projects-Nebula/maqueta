/* Hotmart connection page shell — paste-credential form (POST
 * /api/hotmart/credentials/) plus disconnect button. Mirrors the
 * password-masking pattern in static/storefront/payment-config.js:
 * type=password inputs, autocomplete=off, values never echoed back, blank
 * fields mean "keep the existing stored value" (server-side merge).
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
})();
