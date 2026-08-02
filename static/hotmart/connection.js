/* Hotmart connection page shell — disconnect button only for now
 * (catalog listing + product-to-landing linking land in a later PR).
 * Connect is a plain server-rendered link (302 to Hotmart's authorize
 * endpoint), no JS needed for that half of the flow.
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
  if (!disconnectBtn) return;

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
})();
