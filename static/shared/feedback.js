(function (global) {
  "use strict";

  const timers = new WeakMap();

  function getRegion(target) {
    if (target instanceof Element) return target;
    if (typeof target === "string") return document.querySelector(target);
    let region = document.getElementById("appFeedback");
    if (!region) {
      region = document.createElement("div");
      region.id = "appFeedback";
      region.className = "app-feedback";
      document.body.prepend(region);
    }
    return region;
  }

  function show(message, options = {}) {
    const region = getRegion(options.target);
    if (!region) return;
    const tone = options.tone || "info";
    const persistent = options.persistent === true;
    const timeout = options.timeout == null ? 4800 : options.timeout;
    if (timers.has(region)) clearTimeout(timers.get(region));
    region.textContent = message;
    region.dataset.tone = tone;
    region.setAttribute("role", tone === "error" ? "alert" : "status");
    region.setAttribute("aria-live", tone === "error" ? "assertive" : "polite");
    region.setAttribute("aria-atomic", "true");
    region.classList.add("visible");
    if (!persistent && timeout > 0) {
      timers.set(region, setTimeout(() => region.classList.remove("visible"), timeout));
    }
  }

  function clear(target) {
    const region = getRegion(target);
    if (!region) return;
    if (timers.has(region)) clearTimeout(timers.get(region));
    region.textContent = "";
    region.classList.remove("visible");
  }

  global.AppFeedback = { show, clear };
})(window);
