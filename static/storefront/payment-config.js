/* Owner's payment-gateway configuration page — enable/disable each of the
 * 8 gateways and paste in credentials, against /api/payment-gateway-configs/.
 * Credential FIELD NAMES mirror the server registry for presentation only;
 * validation and encryption remain server-side.
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

  async function responseError(response, fallback) {
    var data = await response.json().catch(function () { return {}; });
    var detail = data.detail || data.error || data.message;
    return detail ? fallback + " " + detail : fallback;
  }

  var list = document.getElementById("gatewayList");
  if (!list) return;

  var GATEWAYS = [
    { gateway: "stripe", label: "Stripe", fields: [["secret_key", "Secret key", "sk_test_... / sk_live_..."], ["webhook_secret", "Webhook signing secret", "whsec_..."]] },
    { gateway: "mercadopago", label: "Mercado Pago", fields: [["access_token", "Access token", "TEST-... / APP_USR-..."], ["webhook_secret", "Webhook secret", "de “Tus integraciones”"]] },
    { gateway: "paypal", label: "PayPal", fields: [["client_id", "Client ID", ""], ["client_secret", "Client secret", ""], ["webhook_id", "Webhook ID", ""]] },
    { gateway: "braintree", label: "Braintree", fields: [["merchant_id", "Merchant ID", ""], ["public_key", "Public key", ""], ["private_key", "Private key", ""]] },
    { gateway: "wompi", label: "Wompi", fields: [["public_key", "Llave pública", "pub_test_... / pub_prod_..."], ["private_key", "Llave privada", "prv_test_... / prv_prod_..."], ["integrity_secret", "Secreto de integridad", ""], ["events_secret", "Secreto de eventos", ""]] },
    { gateway: "payu", label: "PayU", fields: [["merchant_id", "Merchant ID", ""], ["account_id", "Account ID", ""], ["api_key", "API key", ""], ["api_login", "API login", ""]] },
    { gateway: "epayco", label: "ePayco", fields: [["public_key", "Llave pública", ""], ["p_key", "P-Key (privada)", ""], ["p_cust_id_cliente", "ID de cliente", ""]] },
    { gateway: "bold", label: "Bold", fields: [["api_key", "API key", ""], ["secret_key", "Secret key", ""]] },
  ];

  var configsByGateway = {};

  function statusBadge(config) {
    if (!config || !config.is_enabled) return '<span class="gateway-status off">Desactivada</span>';
    var hasAll = config.has_credentials
      ? Object.keys(config.has_credentials).every(function (key) { return config.has_credentials[key]; })
      : false;
    return hasAll
      ? '<span class="gateway-status real">Activa — real</span>'
      : '<span class="gateway-status fake">Activa — prueba (fake)</span>';
  }

  function renderCard(gatewayInfo) {
    var config = configsByGateway[gatewayInfo.gateway];
    var card = document.createElement("section");
    card.className = "gateway-card";
    card.id = "gateway-" + gatewayInfo.gateway;

    var titleId = "gateway-title-" + gatewayInfo.gateway;
    var header = document.createElement("div");
    header.className = "gateway-card-header";
    header.innerHTML = "<div><h2 id=\"" + titleId + "\">" + gatewayInfo.label + "</h2><p class=\"gateway-help\">Las credenciales se guardan protegidas y nunca se vuelven a mostrar.</p></div><div>" + statusBadge(config) + "</div>";
    card.appendChild(header);

    var toggleId = "gateway-toggle-" + gatewayInfo.gateway;
    var gridId = "gateway-credentials-" + gatewayInfo.gateway;
    var toggleRow = document.createElement("label");
    toggleRow.className = "toggle-row";
    toggleRow.setAttribute("for", toggleId);
    var toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.id = toggleId;
    toggle.checked = !!(config && config.is_enabled);
    toggle.setAttribute("aria-controls", gridId);
    var toggleLabel = document.createElement("span");
    toggleLabel.textContent = "Activar esta pasarela";
    toggleRow.appendChild(toggle);
    toggleRow.appendChild(toggleLabel);
    card.appendChild(toggleRow);

    var credentialsGrid = document.createElement("div");
    credentialsGrid.className = "credentials-grid";
    credentialsGrid.id = gridId;
    credentialsGrid.setAttribute("role", "group");
    credentialsGrid.setAttribute("aria-labelledby", titleId);
    var inputs = {};
    gatewayInfo.fields.forEach(function (field) {
      var fieldName = field[0];
      var fieldLabel = field[1];
      var placeholder = field[2];
      var already = config && config.has_credentials && config.has_credentials[fieldName];
      var wrap = document.createElement("label");
      wrap.className = "field";
      var labelText = document.createElement("span");
      labelText.textContent = fieldLabel + (already ? " (ya configurado)" : "");
      wrap.appendChild(labelText);
      var input = document.createElement("input");
      input.className = "control";
      input.type = "password";
      input.name = gatewayInfo.gateway + "-" + fieldName;
      input.autocomplete = "off";
      input.placeholder = already ? "Dejar en blanco para no cambiar" : placeholder;
      wrap.appendChild(input);
      credentialsGrid.appendChild(wrap);
      inputs[fieldName] = input;
    });
    card.appendChild(credentialsGrid);

    function syncGridVisibility() {
      credentialsGrid.classList.toggle("open", toggle.checked);
      credentialsGrid.setAttribute("aria-hidden", String(!toggle.checked));
      toggle.setAttribute("aria-expanded", String(toggle.checked));
    }
    syncGridVisibility();
    toggle.addEventListener("change", syncGridVisibility);

    var actions = document.createElement("div");
    actions.className = "inline-actions";
    var validateBtn = document.createElement("button");
    validateBtn.type = "button";
    validateBtn.className = "btn";
    validateBtn.textContent = "Validar credenciales";
    validateBtn.disabled = !config;
    var saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "btn primary";
    saveBtn.textContent = "Guardar";
    var saveState = document.createElement("span");
    saveState.className = "gateway-save-state";
    saveState.setAttribute("aria-live", "polite");
    actions.appendChild(validateBtn);
    actions.appendChild(saveBtn);
    actions.appendChild(saveState);
    card.appendChild(actions);
    saveBtn.addEventListener("click", function () {
      save(gatewayInfo.gateway, toggle.checked, inputs, saveBtn, card, saveState);
    });
    validateBtn.addEventListener("click", function () {
      validate(gatewayInfo.gateway, validateBtn, saveState);
    });

    return card;
  }

  function renderAll() {
    list.innerHTML = "";
    GATEWAYS.forEach(function (gatewayInfo) {
      list.appendChild(renderCard(gatewayInfo));
    });
    list.setAttribute("aria-busy", "false");
  }

  async function loadConfigs() {
    list.setAttribute("aria-busy", "true");
    list.innerHTML = '<p class="empty-state">Cargando configuración…</p>';
    try {
      var response = await fetch("/api/payment-gateway-configs/", { credentials: "same-origin" });
      if (!response.ok) throw new Error(await responseError(response, "No se pudo cargar la configuración."));
      configsByGateway = {};
      (await response.json()).forEach(function (config) {
        configsByGateway[config.gateway] = config;
      });
      renderAll();
    } catch (error) {
      list.setAttribute("aria-busy", "false");
      list.innerHTML = '<p class="empty-state">No se pudo cargar la configuración. Intentá nuevamente.</p>';
      feedback(error.message || "No se pudo cargar la configuración.", "error");
    }
  }

  async function save(gateway, isEnabled, inputs, button, card, stateLabel) {
    var credentials = {};
    Object.keys(inputs).forEach(function (fieldName) {
      var value = inputs[fieldName].value.trim();
      if (value) credentials[fieldName] = value;
    });

    var existing = configsByGateway[gateway];
    var body = { gateway: gateway, is_enabled: isEnabled, credentials: credentials };
    var url = existing ? "/api/payment-gateway-configs/" + existing.id + "/" : "/api/payment-gateway-configs/";
    var method = existing ? "PATCH" : "POST";
    var originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = "Guardando…";
    card.classList.add("is-saving");
    stateLabel.textContent = "Guardando…";
    try {
      var response = await fetch(url, {
        method: method,
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await responseError(response, "No se pudo guardar."));
      stateLabel.textContent = "Guardado";
      feedback("Configuración de " + gateway + " guardada.", "success");
      await loadConfigs();
    } catch (error) {
      button.disabled = false;
      button.textContent = originalLabel;
      card.classList.remove("is-saving");
      stateLabel.textContent = "No se guardó";
      feedback(error.message || "No se pudo guardar la configuración.", "error");
    }
  }

  async function validate(gateway, button, stateLabel) {
    var config = configsByGateway[gateway];
    if (!config) return;
    var originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = "Validando…";
    stateLabel.textContent = "Validando credenciales guardadas…";
    try {
      var response = await fetch(
        "/api/payment-gateway-configs/" + config.id + "/validate/",
        {
          method: "POST",
          credentials: "same-origin",
          headers: { "X-CSRFToken": getCsrfToken() },
        },
      );
      if (!response.ok) {
        var data = await response.json().catch(function () { return {}; });
        if (data.error === "missing_credentials" && Array.isArray(data.missing)) {
          throw new Error("Faltan: " + data.missing.join(", ") + ".");
        }
        if (data.error === "invalid_credentials") {
          throw new Error("No se pudo inicializar el proveedor con estas credenciales.");
        }
        throw new Error("No se pudieron validar las credenciales.");
      }
      stateLabel.textContent = "Credenciales listas";
      feedback("Las credenciales de " + gateway + " están completas.", "success");
    } catch (error) {
      stateLabel.textContent = "Revisá las credenciales";
      feedback(error.message || "No se pudieron validar las credenciales.", "error");
    } finally {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }

  loadConfigs();
})();
