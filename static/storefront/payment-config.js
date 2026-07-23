/* Owner's payment-gateway configuration page — enable/disable each of the
 * 8 gateways and paste in credentials, against /api/payment-gateway-configs/.
 * Credential FIELD NAMES here mirror apps/storefront/payments.py's
 * GATEWAY_REGISTRY required_fields exactly (presentation-only duplication —
 * these are just form labels, not security logic; the real validation of
 * "is this gateway usable" still happens server-side in build_payment_provider).
 */
(function () {
  "use strict";

  function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  var list = document.getElementById("gatewayList");
  if (!list) return;

  var GATEWAYS = [
    {
      gateway: "stripe",
      label: "Stripe",
      fields: [
        ["secret_key", "Secret key", "sk_test_... / sk_live_..."],
        ["webhook_secret", "Webhook signing secret", "whsec_..."]
      ]
    },
    {
      gateway: "mercadopago",
      label: "Mercado Pago",
      fields: [
        ["access_token", "Access token", "TEST-... / APP_USR-..."],
        ["webhook_secret", "Webhook secret", "de “Tus integraciones”"]
      ]
    },
    {
      gateway: "paypal",
      label: "PayPal",
      fields: [
        ["client_id", "Client ID", ""],
        ["client_secret", "Client secret", ""],
        ["webhook_id", "Webhook ID", ""]
      ]
    },
    {
      gateway: "braintree",
      label: "Braintree",
      fields: [
        ["merchant_id", "Merchant ID", ""],
        ["public_key", "Public key", ""],
        ["private_key", "Private key", ""]
      ]
    },
    {
      gateway: "wompi",
      label: "Wompi",
      fields: [
        ["public_key", "Llave pública", "pub_test_... / pub_prod_..."],
        ["private_key", "Llave privada", "prv_test_... / prv_prod_..."],
        ["integrity_secret", "Secreto de integridad", ""],
        ["events_secret", "Secreto de eventos", ""]
      ]
    },
    {
      gateway: "payu",
      label: "PayU",
      fields: [
        ["merchant_id", "Merchant ID", ""],
        ["account_id", "Account ID", ""],
        ["api_key", "API key", ""],
        ["api_login", "API login", ""]
      ]
    },
    {
      gateway: "epayco",
      label: "ePayco",
      fields: [
        ["public_key", "Llave pública", ""],
        ["p_key", "P-Key (privada)", ""],
        ["p_cust_id_cliente", "ID de cliente", ""]
      ]
    },
    {
      gateway: "bold",
      label: "Bold",
      fields: [
        ["api_key", "API key", ""],
        ["secret_key", "Secret key", ""]
      ]
    }
  ];

  var configsByGateway = {};

  function statusBadge(config) {
    if (!config || !config.is_enabled) {
      return '<span class="gateway-status off">Desactivada</span>';
    }
    var hasAll = config.has_credentials
      ? Object.keys(config.has_credentials).every(function (k) { return config.has_credentials[k]; })
      : false;
    return hasAll
      ? '<span class="gateway-status real">Activa — real</span>'
      : '<span class="gateway-status fake">Activa — prueba (fake)</span>';
  }

  function renderCard(gatewayInfo) {
    var config = configsByGateway[gatewayInfo.gateway];
    var card = document.createElement("div");
    card.className = "gateway-card";

    var header = document.createElement("div");
    header.className = "gateway-card-header";
    header.innerHTML =
      "<h2>" + gatewayInfo.label + "</h2><div>" + statusBadge(config) + "</div>";
    card.appendChild(header);

    var toggleRow = document.createElement("label");
    toggleRow.className = "toggle-row";
    var toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.checked = !!(config && config.is_enabled);
    var toggleLabel = document.createElement("span");
    toggleLabel.textContent = "Activar esta pasarela";
    toggleRow.appendChild(toggle);
    toggleRow.appendChild(toggleLabel);
    card.appendChild(toggleRow);

    var credentialsGrid = document.createElement("div");
    credentialsGrid.className = "credentials-grid";
    var inputs = {};
    gatewayInfo.fields.forEach(function (field) {
      var fieldName = field[0];
      var fieldLabel = field[1];
      var placeholder = field[2];
      var already = config && config.has_credentials && config.has_credentials[fieldName];
      var wrap = document.createElement("label");
      wrap.className = "field";
      wrap.innerHTML =
        "<span>" + fieldLabel + (already ? ' <span class="hint">(ya configurado)</span>' : "") + "</span>";
      var input = document.createElement("input");
      input.className = "control";
      input.type = "password";
      input.placeholder = already ? "Dejar en blanco para no cambiar" : placeholder;
      wrap.appendChild(input);
      credentialsGrid.appendChild(wrap);
      inputs[fieldName] = input;
    });
    card.appendChild(credentialsGrid);

    function syncGridVisibility() {
      credentialsGrid.classList.toggle("open", toggle.checked);
    }
    syncGridVisibility();
    toggle.addEventListener("change", syncGridVisibility);

    var saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "btn primary";
    saveBtn.textContent = "Guardar";
    saveBtn.addEventListener("click", function () {
      save(gatewayInfo.gateway, toggle.checked, inputs);
    });
    card.appendChild(saveBtn);

    return card;
  }

  function renderAll() {
    list.innerHTML = "";
    GATEWAYS.forEach(function (gatewayInfo) {
      list.appendChild(renderCard(gatewayInfo));
    });
  }

  async function loadConfigs() {
    var response = await fetch("/api/payment-gateway-configs/", { credentials: "same-origin" });
    if (!response.ok) return;
    var configs = await response.json();
    configsByGateway = {};
    configs.forEach(function (c) { configsByGateway[c.gateway] = c; });
    renderAll();
  }

  async function save(gateway, isEnabled, inputs) {
    var credentials = {};
    Object.keys(inputs).forEach(function (fieldName) {
      var value = inputs[fieldName].value.trim();
      if (value) credentials[fieldName] = value; // blank = "don't change this field"
    });

    var existing = configsByGateway[gateway];
    var body = { gateway: gateway, is_enabled: isEnabled, credentials: credentials };
    var url = existing ? "/api/payment-gateway-configs/" + existing.id + "/" : "/api/payment-gateway-configs/";
    var method = existing ? "PATCH" : "POST";

    var response = await fetch(url, {
      method: method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
      body: JSON.stringify(body)
    });
    if (!response.ok) {
      var data = await response.json().catch(function () { return {}; });
      alert("No se pudo guardar: " + JSON.stringify(data));
      return;
    }
    await loadConfigs();
  }

  loadConfigs();
})();
