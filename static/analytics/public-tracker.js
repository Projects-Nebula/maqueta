(function () {
  "use strict";

  var script = document.currentScript || document.querySelector("script[data-template-slug]");
  var consentRoot = document.getElementById("analyticsConsent");
  var templateSlug = script && script.dataset.templateSlug;
  if (!consentRoot || !templateSlug) return;

  var COLLECT_URL = "/api/analytics/collect/";
  var CONSENT_URL = "/api/analytics/consent/";
  var MAX_QUEUE = 80;
  var FLUSH_INTERVAL = 5000;
  var MOVE_INTERVAL = 650;
  var started = false;
  var ended = false;
  var flushing = false;
  var sessionId = null;
  var queue = [];
  var startedAt = Date.now();
  var lastMoveAt = 0;

  function readCookie(name) {
    var prefix = name + "=";
    var cookies = document.cookie.split(";");
    for (var index = 0; index < cookies.length; index += 1) {
      var cookie = cookies[index].trim();
      if (cookie.indexOf(prefix) === 0) return decodeURIComponent(cookie.slice(prefix.length));
    }
    return "";
  }

  function clamp(value) {
    return Math.max(0, Math.min(1, value));
  }

  function viewport() {
    return {
      viewport_width: Math.min(window.innerWidth || 0, 10000),
      viewport_height: Math.min(window.innerHeight || 0, 10000),
    };
  }

  function point(event) {
    var width = Math.max(document.documentElement.clientWidth || window.innerWidth || 1, 1);
    var height = Math.max(document.documentElement.scrollHeight || window.innerHeight || 1, 1);
    return {
      x: Number(clamp(event.clientX / width).toFixed(5)),
      y: Number(clamp((event.clientY + window.scrollY) / height).toFixed(5)),
    };
  }

  function targetDescriptor(element) {
    if (!element || !element.tagName) return "";
    var tag = element.tagName.toLowerCase();
    var id = element.id || "";
    if (!/^[A-Za-z][A-Za-z0-9_-]{0,40}$/.test(id)) id = "";
    var role = element.getAttribute("role") || "";
    if (!/^[A-Za-z][A-Za-z0-9_-]{0,24}$/.test(role)) role = "";
    return tag + (id ? "#" + id : "") + (role ? "[" + role + "]" : "");
  }

  function eventPayload(kind, extra) {
    var data = Object.assign({ kind: kind }, viewport(), extra || {});
    if (kind !== "click" && kind !== "move") {
      delete data.x;
      delete data.y;
    }
    return data;
  }

  function enqueue(event) {
    if (ended) return;
    if (queue.length >= MAX_QUEUE) {
      var moveIndex = queue.findIndex(function (item) { return item.kind === "move"; });
      if (moveIndex >= 0) queue.splice(moveIndex, 1);
      else return;
    }
    queue.push(event);
    if (queue.length >= 20) flush(false);
  }

  function requeue(events) {
    queue = events.concat(queue).slice(-MAX_QUEUE);
  }

  async function flush(useBeacon) {
    if (!started || !queue.length || flushing) return;
    var events = queue.splice(0, MAX_QUEUE);
    var payload = JSON.stringify({
      template_slug: templateSlug,
      session_id: sessionId,
      entry_path: window.location.pathname,
      events: events,
    });
    if (useBeacon && navigator.sendBeacon) {
      var blob = new Blob([payload], { type: "application/json" });
      navigator.sendBeacon(COLLECT_URL, blob);
      return;
    }
    flushing = true;
    try {
      var response = await fetch(COLLECT_URL, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true,
      });
      if (!response.ok) {
        if (response.status === 403) ended = true;
        else requeue(events);
        return;
      }
      var data = await response.json();
      sessionId = data.session_id || sessionId;
    } catch (error) {
      requeue(events);
    } finally {
      flushing = false;
      if (queue.length && !ended) flush(false);
    }
  }

  function elapsedMs() {
    return Math.min(Math.max(Date.now() - startedAt, 0), 24 * 60 * 60 * 1000);
  }

  function start() {
    if (started || ended) return;
    started = true;
    consentRoot.remove();
    enqueue(eventPayload("pageview", { duration_ms: 0 }));
    flush(false);

    window.setInterval(function () {
      enqueue(eventPayload("heartbeat", { duration_ms: elapsedMs() }));
      flush(false);
    }, 15000);

    document.addEventListener("click", function (event) {
      var coordinates = point(event);
      enqueue(eventPayload("click", {
        x: coordinates.x,
        y: coordinates.y,
        target: targetDescriptor(event.target),
      }));
    }, { passive: true });

    document.addEventListener("pointermove", function (event) {
      if (event.pointerType && event.pointerType !== "mouse") return;
      var now = Date.now();
      if (now - lastMoveAt < MOVE_INTERVAL) return;
      lastMoveAt = now;
      var coordinates = point(event);
      enqueue(eventPayload("move", { x: coordinates.x, y: coordinates.y }));
    }, { passive: true });

    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") {
        enqueue(eventPayload("heartbeat", { duration_ms: elapsedMs() }));
        flush(true);
      }
    });

    window.addEventListener("pagehide", function () {
      if (ended) return;
      ended = true;
      queue.push(eventPayload("page_exit", { duration_ms: elapsedMs() }));
      flush(true);
    });

    window.setInterval(function () { flush(false); }, FLUSH_INTERVAL);
  }

  function postConsent(decision, button) {
    button.disabled = true;
    fetch(CONSENT_URL, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision: decision }),
      keepalive: true,
    }).then(function (response) {
      if (!response.ok) throw new Error("consent failed");
      if (decision === "accepted") start();
      else consentRoot.remove();
    }).catch(function () {
      button.disabled = false;
      consentRoot.querySelector(".analytics-consent-error").textContent = "No se pudo guardar tu elección. Intentá de nuevo.";
    });
  }

  function renderConsent() {
    var consent = readCookie("analytics_consent");
    if (consent === "accepted") {
      start();
      return;
    }
    if (consent === "declined") {
      consentRoot.remove();
      return;
    }
    consentRoot.className = "analytics-consent";
    consentRoot.setAttribute("role", "dialog");
    consentRoot.setAttribute("aria-labelledby", "analyticsConsentTitle");
    consentRoot.innerHTML = "";

    var title = document.createElement("strong");
    title.id = "analyticsConsentTitle";
    title.textContent = "Ayudanos a mejorar esta página";
    consentRoot.appendChild(title);

    var copy = document.createElement("p");
    copy.textContent = "Usamos analítica anónima para entender visitas y mejorar la experiencia. No registramos formularios ni datos personales.";
    consentRoot.appendChild(copy);

    var actions = document.createElement("div");
    actions.className = "analytics-consent-actions";
    var accept = document.createElement("button");
    accept.type = "button";
    accept.className = "analytics-consent-accept";
    accept.textContent = "Aceptar analítica";
    var decline = document.createElement("button");
    decline.type = "button";
    decline.className = "analytics-consent-decline";
    decline.textContent = "No, gracias";
    var error = document.createElement("span");
    error.className = "analytics-consent-error";
    error.setAttribute("role", "alert");
    actions.appendChild(accept);
    actions.appendChild(decline);
    actions.appendChild(error);
    consentRoot.appendChild(actions);
    accept.addEventListener("click", function () { postConsent("accepted", accept); });
    decline.addEventListener("click", function () { postConsent("declined", decline); });
  }

  renderConsent();
})();
