/* AI assistant panel + deterministic operation applier.
 *
 * applyAIOperations is a pure function (state, operations) -> new state so it
 * can be unit-tested in Node. It never uses eval and never executes strings.
 */
(function (global) {
  "use strict";

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function bodyChildren(state) {
    return state.document.body.children;
  }

  function getNodeAt(state, path) {
    let children = bodyChildren(state);
    let node = null;
    for (const index of path) {
      node = children[index];
      if (!node) return null;
      children = node.children || [];
    }
    return node;
  }

  function parentInfo(state, path) {
    if (!Array.isArray(path) || path.length === 0) {
      return { children: bodyChildren(state), index: null };
    }
    const parentPath = path.slice(0, -1);
    const index = path[path.length - 1];
    if (parentPath.length === 0) {
      return { children: bodyChildren(state), index };
    }
    const parent = getNodeAt(state, parentPath);
    if (!parent) {
      // Parent path drifted from reality (e.g. it was itself removed by an
      // earlier op in this batch) — an empty array makes children[index]
      // reliably undefined, so callers' "not found" guard fires instead of
      // silently mutating an unrelated node at the same index in the body.
      return { children: [], index };
    }
    parent.children = parent.children || [];
    return { children: parent.children, index };
  }

  function findRefParent(children, target) {
    for (let i = 0; i < children.length; i += 1) {
      if (children[i] === target) return { children, index: i };
      const kids = children[i] && children[i].children;
      if (Array.isArray(kids)) {
        const found = findRefParent(kids, target);
        if (found) return found;
      }
    }
    return null;
  }

  function isPrefix(prefix, path) {
    return prefix.length <= path.length && prefix.every((v, i) => v === path[i]);
  }

  function ensureRule(state, selector) {
    state.styles = state.styles || {};
    state.styles.rules = state.styles.rules || [];
    let rule = state.styles.rules.find((r) => r.selector === selector);
    if (!rule) {
      rule = { selector, declarations: {} };
      state.styles.rules.push(rule);
    }
    rule.declarations = rule.declarations || {};
    return rule;
  }

  function applyOne(state, op) {
    switch (op.action) {
      case "set_text": {
        const node = getNodeAt(state, op.path);
        if (!node) throw new Error("set_text: node not found");
        node.value = op.value;
        return;
      }
      case "set_attribute": {
        const node = getNodeAt(state, op.path);
        if (!node) throw new Error("set_attribute: node not found");
        node.attributes = node.attributes || {};
        node.attributes[op.attribute] = op.value;
        return;
      }
      case "remove_attribute": {
        const node = getNodeAt(state, op.path);
        if (!node || !node.attributes) return;
        delete node.attributes[op.attribute];
        return;
      }
      case "set_style_variable": {
        state.styles = state.styles || {};
        state.styles.variables = state.styles.variables || {};
        state.styles.variables[op.name] = op.value;
        return;
      }
      case "set_css_declaration": {
        ensureRule(state, op.selector).declarations[op.property] = op.value;
        return;
      }
      case "remove_css_declaration": {
        const rule = (state.styles && state.styles.rules || []).find(
          (r) => r.selector === op.selector
        );
        if (rule && rule.declarations) delete rule.declarations[op.property];
        return;
      }
      case "add_node":
      case "add_section": {
        const parentPath = op.parent_path || [];
        const parent = parentPath.length ? getNodeAt(state, parentPath) : null;
        const children = parent ? (parent.children || (parent.children = [])) : bodyChildren(state);
        const index = Math.min(op.index == null ? children.length : op.index, children.length);
        children.splice(index, 0, clone(op.node));
        return;
      }
      case "replace_node": {
        const { children, index } = parentInfo(state, op.path);
        if (children[index] === undefined) throw new Error("replace_node: not found");
        children[index] = clone(op.node);
        return;
      }
      case "duplicate_node": {
        const { children, index } = parentInfo(state, op.path);
        if (children[index] === undefined) throw new Error("duplicate_node: not found");
        children.splice(index + 1, 0, clone(children[index]));
        return;
      }
      case "delete_node": {
        const { children, index } = parentInfo(state, op.path);
        if (children[index] === undefined) throw new Error("delete_node: not found");
        children.splice(index, 1);
        return;
      }
      case "move_node": {
        // Cycle guard (defence in depth; the backend already blocks this).
        if (isPrefix(op.source_path, op.target_path)) {
          throw new Error("move_node: cannot move a node into itself");
        }
        const target = getNodeAt(state, op.target_path);
        if (!target) throw new Error("move_node: target not found");
        const src = parentInfo(state, op.source_path);
        const moved = src.children[src.index];
        if (moved === undefined) throw new Error("move_node: source not found");
        src.children.splice(src.index, 1);

        if (op.position === "inside") {
          target.children = target.children || [];
          target.children.push(moved);
          return;
        }
        const ref = findRefParent(bodyChildren(state), target);
        if (!ref) throw new Error("move_node: target lost after removal");
        const at = op.position === "after" ? ref.index + 1 : ref.index;
        ref.children.splice(at, 0, moved);
        return;
      }
      default:
        throw new Error("unknown action: " + op.action);
    }
  }

  function applyAIOperations(documentState, operations) {
    if (!Array.isArray(operations)) throw new Error("operations must be an array");
    const next = clone(documentState);
    for (const op of operations) {
      applyOne(next, op);
    }
    return next;
  }

  // --- Node export (tests) --------------------------------------------------
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { applyAIOperations };
    return;
  }

  // --- Browser panel wiring -------------------------------------------------
  global.applyAIOperations = applyAIOperations;

  const config = JSON.parse(document.getElementById("editor-config").textContent);
  const els = {
    contextChip: document.getElementById("aiContextChip"),
    composerRef: document.getElementById("aiComposerRef"),
    globalMode: document.getElementById("aiGlobalMode"),
    messages: document.getElementById("aiMessages"),
    input: document.getElementById("aiComposerInput"),
    send: document.getElementById("aiComposerSend"),
    fab: document.getElementById("aiFab"),
    drawer: document.getElementById("aiDrawer"),
    drawerClose: document.getElementById("aiDrawerClose"),
  };

  let requestInFlight = false;
  let drawerRestoreFocusTarget = null;

  // Read the CSRF token Django set as a cookie (ensure_csrf_cookie on the view).
  function getCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function scrollMessagesToBottom() {
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function appendUserBubble(text, ref) {
    const wrap = document.createElement("div");
    wrap.className = "ai-msg ai-msg-user";
    const bubble = document.createElement("div");
    bubble.className = "ai-bubble";
    if (ref) {
      const refEl = document.createElement("span");
      refEl.className = "ai-ref";
      refEl.textContent = `#${ref}`;
      bubble.appendChild(refEl);
      bubble.appendChild(document.createTextNode(" "));
    }
    bubble.appendChild(document.createTextNode(text));
    wrap.appendChild(bubble);
    els.messages.appendChild(wrap);
    scrollMessagesToBottom();
    return wrap;
  }

  function appendTypingBubble() {
    return global.AIStream.createTypingBubble({
      messages: els.messages,
      scrollToBottom: scrollMessagesToBottom,
      statusMessages: [
        "Analizando tu página…",
        "Pensando el diseño…",
        "Generando los cambios…",
        "Casi listo…",
      ],
    });
  }

  function appendErrorBubble(message) {
    const wrap = document.createElement("div");
    wrap.className = "ai-msg ai-msg-assistant";
    const bubble = document.createElement("div");
    bubble.className = "ai-bubble ai-bubble-error";
    bubble.textContent = message;
    wrap.appendChild(bubble);
    els.messages.appendChild(wrap);
    scrollMessagesToBottom();
    return wrap;
  }

  // Friendly, human-readable labels for the CSS properties the AI touches.
  const CSS_LABELS = {
    "background-color": "Fondo",
    background: "Fondo",
    color: "Color de texto",
    "border-radius": "Bordes redondeados",
    "border-color": "Color de borde",
    "font-size": "Tamaño de texto",
    "font-weight": "Grosor de texto",
    "text-align": "Alineación",
    padding: "Espaciado interno",
    margin: "Margen",
    width: "Ancho",
    height: "Alto",
    gap: "Separación",
    "box-shadow": "Sombra",
    opacity: "Opacidad",
  };

  function truncate(value, max) {
    const s = String(value == null ? "" : value);
    return s.length > max ? s.slice(0, max - 1) + "…" : s;
  }

  function nodeLabel(node) {
    return node && node.tag ? `<${node.tag}>` : "elemento";
  }

  // Turns a raw operation into a phrase a non-technical user understands.
  function describeOperation(op) {
    switch (op.action) {
      case "set_text":
        return `Texto: “${truncate(op.value, 40)}”`;
      case "set_attribute": {
        const v = Array.isArray(op.value) ? op.value.join(" ") : op.value;
        if (op.attribute === "class") return `Estilo/clase: ${truncate(v, 40)}`;
        return `${op.attribute}: ${truncate(v, 40)}`;
      }
      case "remove_attribute":
        return `Quitar ${op.attribute}`;
      case "set_style_variable":
        return `${CSS_LABELS[op.name] || op.name}: ${op.value}`;
      case "set_css_declaration":
        return `${CSS_LABELS[op.property] || op.property}: ${op.value}`;
      case "remove_css_declaration":
        return `Quitar ${CSS_LABELS[op.property] || op.property}`;
      case "add_node":
        return `Agregar ${nodeLabel(op.node)}`;
      case "add_section":
        return "Agregar sección";
      case "replace_node":
        return "Reemplazar elemento";
      case "duplicate_node":
        return "Duplicar elemento";
      case "delete_node":
        return "Eliminar elemento";
      case "move_node":
        return "Mover elemento";
      default:
        return op.action;
    }
  }

  // Renders an assistant bubble for a change that was ALREADY applied. Shows
  // the summary + operations and a "Descartar" button that reverts to the
  // state captured just before this change (beforeState).
  function appendAppliedBubble(summary, operations, beforeState, reasoning) {
    const wrap = document.createElement("div");
    wrap.className = "ai-msg ai-msg-assistant";

    const bubble = document.createElement("div");
    bubble.className = "ai-bubble ai-bubble-assistant";

    const summaryEl = document.createElement("p");
    summaryEl.className = "ai-bubble-summary";
    summaryEl.textContent = summary || "Sin resumen.";
    bubble.appendChild(summaryEl);

    if (typeof reasoning === "string" && reasoning.trim()) {
      const reasoningDetails = document.createElement("details");
      reasoningDetails.className = "ai-bubble-reasoning-details";
      const reasoningToggle = document.createElement("summary");
      reasoningToggle.textContent = "Ver razonamiento";
      reasoningDetails.appendChild(reasoningToggle);
      const reasoningText = document.createElement("p");
      reasoningText.className = "ai-bubble-reasoning";
      reasoningText.textContent = reasoning.trim();
      reasoningDetails.appendChild(reasoningText);
      bubble.appendChild(reasoningDetails);
    }

    if (Array.isArray(operations) && operations.length) {
      const details = document.createElement("details");
      details.className = "ai-bubble-ops-details";
      const toggle = document.createElement("summary");
      toggle.textContent =
        operations.length === 1 ? "Ver 1 cambio" : `Ver ${operations.length} cambios`;
      details.appendChild(toggle);
      const list = document.createElement("ul");
      list.className = "ai-bubble-ops";
      operations.forEach((op) => {
        const li = document.createElement("li");
        li.textContent = describeOperation(op);
        list.appendChild(li);
      });
      details.appendChild(list);
      bubble.appendChild(details);
    }

    const status = document.createElement("div");
    status.className = "ai-bubble-note";
    status.textContent = "✓ Aplicado";
    bubble.appendChild(status);

    const actions = document.createElement("div");
    actions.className = "ai-bubble-actions";
    const discardBtn = document.createElement("button");
    discardBtn.type = "button";
    discardBtn.className = "btn small";
    discardBtn.textContent = "Descartar cambio";
    actions.appendChild(discardBtn);
    bubble.appendChild(actions);

    wrap.appendChild(bubble);
    els.messages.appendChild(wrap);
    scrollMessagesToBottom();

    let reverted = false;
    discardBtn.addEventListener("click", () => {
      if (reverted) return;
      reverted = true;
      // Restore the snapshot from before this change (its own undo step).
      global.EditorCore.commitProposal(beforeState);
      actions.remove();
      status.textContent = "Descartado";
      status.classList.add("discarded");
    });
  }

  // Global mode defaults to ON while nothing specific is selected, and OFF the
  // moment an element is. Only acts on the transition (not every poll tick) so
  // a manual toggle by the user is never fought while selection stays the same.
  let lastHadSelection = null;
  function syncGlobalModeDefault() {
    const hasSelection = !!global.EditorCore.getSelectedPath();
    if (hasSelection === lastHadSelection) return;
    lastHadSelection = hasSelection;
    els.globalMode.checked = !hasSelection;
  }

  function updateContextChip() {
    const path = global.EditorCore.getSelectedPath();
    if (els.globalMode.checked || !path) {
      els.contextChip.textContent = els.globalMode.checked
        ? "Modo global: se enviará el resumen de la página."
        : "Ningún elemento seleccionado.";
      els.composerRef.classList.add("hidden");
      return;
    }
    const node = global.EditorCore.getSelectedNode();
    const tag = node && node.tag ? `<${node.tag}>` : node && node.type;
    els.contextChip.textContent = `Editando: ${tag}`;
    els.composerRef.textContent = `@${node && node.type}`;
    els.composerRef.classList.remove("hidden");
  }

  function setBusy(isBusy) {
    requestInFlight = isBusy;
    els.send.disabled = isBusy;
    els.input.disabled = isBusy;
  }

  function autoResizeInput() {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(els.input.scrollHeight, 120) + "px";
  }

  els.globalMode.addEventListener("change", updateContextChip);
  els.input.addEventListener("input", autoResizeInput);

  async function sendMessage() {
    if (requestInFlight) return;
    const instruction = els.input.value.trim();
    if (!instruction) return;

    const globalMode = els.globalMode.checked;
    const selectedPath = global.EditorCore.getSelectedPath();
    if (!globalMode && !selectedPath) {
      appendErrorBubble("Selecciona un elemento en la vista previa o activa el modo global.");
      return;
    }

    const refNode = globalMode ? null : global.EditorCore.getSelectedNode();
    appendUserBubble(instruction, refNode && refNode.type);
    els.input.value = "";
    autoResizeInput();

    const parentPath = selectedPath ? selectedPath.slice(0, -1) : null;
    const parentNode = parentPath ? global.EditorCore.getNodeAt(parentPath) : null;
    const payload = {
      instruction,
      global_mode: globalMode,
      selected_path: globalMode ? null : selectedPath,
      selected_node: globalMode ? null : global.EditorCore.getSelectedNode(),
      parent_context: parentNode ? { tag: parentNode.tag, attributes: parentNode.attributes } : {},
      sibling_context: parentNode && parentNode.children
        ? parentNode.children.map((c) => ({ type: c.type, tag: c.tag })).slice(0, 20)
        : [],
      design_variables: global.EditorCore.getDesignVariables(),
      page_summary: global.EditorCore.getPageSummary(),
      body_outline: global.EditorCore.getBodyOutline().slice(0, 40),
    };

    setBusy(true);
    const typingBubble = appendTypingBubble();
    try {
      const response = await fetch(config.endpoints.transform, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(payload),
      });

      // Input validation (400/401/403/429) short-circuits before streaming
      // starts and comes back as a plain JSON body, not an event stream.
      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("text/event-stream")) {
        const data = await response.json().catch(() => ({}));
        typingBubble.remove();
        appendErrorBubble(errorMessage(data, response.status));
        return;
      }

      const { done: doneEvent, error: errorEvent } = await global.AIStream.consume(
        response,
        (reasoningSoFar) => typingBubble.setReasoning(reasoningSoFar)
      );
      typingBubble.remove();

      if (errorEvent) {
        appendErrorBubble(errorMessage(errorEvent, 0));
        return;
      }
      if (!doneEvent) {
        appendErrorBubble("No se pudieron generar los cambios.");
        return;
      }

      // Auto-apply the change immediately (one undo step); the bubble keeps a
      // "Descartar" button that reverts to the snapshot from before it.
      const beforeState = global.EditorCore.getState();
      let nextState;
      try {
        nextState = applyAIOperations(beforeState, doneEvent.operations);
      } catch (applyErr) {
        // The server already validated these operations in isolation, but a
        // large batch can still drift from the live tree (an earlier op in
        // the same batch moves/removes what a later op's path expects).
        // eslint-disable-next-line no-console
        console.error("editor-ai apply failed:", applyErr, doneEvent.operations);
        appendErrorBubble("La IA propuso cambios que no se pudieron aplicar. Intenta reformular.");
        return;
      }
      global.EditorCore.commitProposal(nextState);
      appendAppliedBubble(doneEvent.summary, doneEvent.operations, beforeState, doneEvent.reasoning);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("editor-ai transform failed:", err);
      typingBubble.remove();
      appendErrorBubble("No se pudo contactar al asistente.");
    } finally {
      setBusy(false);
    }
  }

  els.send.addEventListener("click", sendMessage);

  // Programmatic entry point for other editor controls (e.g. "Insertar
  // producto") that want the AI to design/insert something instead of a
  // hardcoded template — always global_mode since there's no relevant
  // selected element for these.
  global.EditorAI = {
    requestInstruction(instructionText) {
      openDrawer();
      els.globalMode.checked = true;
      updateContextChip();
      els.input.value = instructionText;
      sendMessage();
    },
  };

  els.input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });

  function openDrawer() {
    drawerRestoreFocusTarget = document.activeElement !== document.body ? document.activeElement : null;
    els.drawer.classList.remove("hidden");
    els.drawer.setAttribute("aria-hidden", "false");
    els.fab.setAttribute("aria-expanded", "true");
    els.input.focus();
  }

  function closeDrawer() {
    els.drawer.classList.add("hidden");
    els.drawer.setAttribute("aria-hidden", "true");
    els.fab.setAttribute("aria-expanded", "false");
    if (drawerRestoreFocusTarget && document.contains(drawerRestoreFocusTarget)) {
      drawerRestoreFocusTarget.focus();
    }
    drawerRestoreFocusTarget = null;
  }

  els.fab.addEventListener("click", () => {
    if (els.drawer.classList.contains("hidden")) {
      openDrawer();
    } else {
      closeDrawer();
    }
  });

  els.drawerClose.addEventListener("click", closeDrawer);

  document.addEventListener("keydown", (event) => {
    if (els.drawer.classList.contains("hidden")) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeDrawer();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = focusableElements(els.drawer);
    if (!focusable.length) {
      event.preventDefault();
      els.drawerClose.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  function errorMessage(data, status) {
    const code = data && data.error;
    const map = {
      invalid_operations: "La IA propuso cambios no válidos. Intenta reformular.",
      ai_timeout: "El asistente tardó demasiado. Reintenta.",
      ai_unavailable: "El asistente no está disponible ahora.",
      unexpected_error: "Ocurrió un error inesperado. Revisa el registro del servidor.",
    };
    if (code === "invalid_input") {
      return data.detail
        ? `Solicitud no válida (${data.detail}).`
        : "El elemento seleccionado o la instrucción no son válidos.";
    }
    if (map[code]) return map[code];
    if (status === 401 || status === 403) return "Sesión expirada. Vuelve a iniciar sesión.";
    if (status === 429) return "Demasiadas solicitudes. Espera un momento.";
    return "No se pudieron generar los cambios.";
  }

  // --- Floating action buttons on the selected preview element -------------
  // The buttons only forward to the existing #duplicateButton / #deleteButton
  // handlers, so all the tree-mutation + selection cleanup logic stays in the
  // editor core (which we do not touch). We only draw and position the UI.
  const ACTION_STYLE =
    ".vjpb-actions{position:absolute;display:flex;gap:4px;z-index:2147483647;" +
    "transform:translate(-100%,-100%);padding-bottom:4px;}" +
    ".vjpb-action{width:24px;height:24px;display:flex;align-items:center;" +
    "justify-content:center;border:none;border-radius:6px;background:#5b5ce2;" +
    "color:#fff;font-size:13px;line-height:1;padding:0;cursor:pointer;" +
    "box-shadow:0 2px 6px rgba(0,0,0,.25);}" +
    ".vjpb-action:hover{filter:brightness(1.12);}" +
    ".vjpb-action.vjpb-danger{background:#e2555e;}";

  function makeActionButton(doc, label, glyph, onActivate, danger) {
    const btn = doc.createElement("button");
    btn.type = "button";
    btn.className = danger ? "vjpb-action vjpb-danger" : "vjpb-action";
    btn.title = label;
    btn.setAttribute("aria-label", label);
    btn.textContent = glyph;
    btn.addEventListener("mousedown", (e) => e.stopPropagation());
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      onActivate();
    });
    return btn;
  }

  // Forward to an existing parent-document button (reuses its wired handler).
  function clickParent(id) {
    const target = document.getElementById(id);
    if (target) target.click();
  }

  // All editor dialogs share one backdrop and one keyboard/focus policy. Keeping
  // this here avoids save-template.js and editor-core.js each growing their own
  // slightly different modal implementation.
  const elementModal = document.getElementById("elementModal");
  const sectionModal = document.getElementById("sectionModal");
  const editorBackdrop = document.getElementById("editorModalBackdrop");
  // Every real modal shares this class + role, template-defined or not —
  // queried once at load rather than a hand-maintained id list, so a new
  // modal added to editor.html (e.g. htmlImportModal, missed here once
  // already) is picked up automatically instead of silently never opening.
  // register() below extends this for modals built dynamically in JS
  // (e.g. the command palette), which don't exist yet at this query time.
  const modalElements = [...document.querySelectorAll('.panel-modal[role="dialog"]')];
  let activeModal = null;
  let restoreFocusTarget = null;

  function focusableElements(container) {
    return [...container.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )].filter(element => {
      const style = window.getComputedStyle(element);
      return style.display !== "none" && style.visibility !== "hidden";
    });
  }

  function setModalVisibility(modal, visible) {
    modal.classList.toggle("hidden", !visible);
    modal.setAttribute("aria-hidden", String(!visible));
  }

  function closeAllModals({ restoreFocus = true } = {}) {
    modalElements.forEach(modal => {
      setModalVisibility(modal, false);
      document.querySelectorAll(`[aria-controls="${modal.id}"]`).forEach(trigger => {
        trigger.setAttribute("aria-expanded", "false");
      });
    });
    if (editorBackdrop) editorBackdrop.classList.add("hidden");
    const target = restoreFocus ? restoreFocusTarget : null;
    activeModal = null;
    restoreFocusTarget = null;
    if (target && document.contains(target) && !target.disabled) target.focus();
  }

  function openModal(el, trigger = document.activeElement) {
    if (!el) return;
    closeAllModals({ restoreFocus: false });
    modalElements.forEach(modal => setModalVisibility(modal, modal === el));
    if (editorBackdrop) editorBackdrop.classList.remove("hidden");
    activeModal = el;
    restoreFocusTarget = trigger && trigger !== document.body ? trigger : null;
    if (restoreFocusTarget && restoreFocusTarget.setAttribute) {
      restoreFocusTarget.setAttribute("aria-controls", el.id);
      restoreFocusTarget.setAttribute("aria-expanded", "true");
    }
    const firstFocusable = focusableElements(el)[0];
    if (firstFocusable) firstFocusable.focus();
  }

  global.EditorModals = {
    closeAll: closeAllModals,
    open: openModal,
    isOpen: () => Boolean(activeModal),
    getActive: () => activeModal,
    // For modals built dynamically in JS after this script already ran its
    // one-time query above (e.g. the command palette) — a no-op if el is
    // already registered, so callers don't need to track that themselves.
    register: (el) => {
      if (el && !modalElements.includes(el)) modalElements.push(el);
    }
  };

  function openEditorModal() {
    openModal(elementModal);
  }
  function clickTab(name) {
    const tab = document.querySelector('.tab[data-tab="' + name + '"]');
    if (tab) tab.click();
  }
  const editorClose = document.getElementById("editorModalClose");
  if (editorClose) editorClose.addEventListener("click", closeAllModals);
  const sectionClose = document.getElementById("sectionModalClose");
  if (sectionClose) sectionClose.addEventListener("click", closeAllModals);
  const paymentLinkClose = document.getElementById("paymentLinkModalClose");
  if (paymentLinkClose) paymentLinkClose.addEventListener("click", closeAllModals);
  const imagePickerClose = document.getElementById("imagePickerModalClose");
  if (imagePickerClose) imagePickerClose.addEventListener("click", closeAllModals);
  if (editorBackdrop) editorBackdrop.addEventListener("click", () => closeAllModals());
  document.querySelectorAll(".section-open").forEach((btn) => {
    btn.addEventListener("click", () => {
      clickTab(btn.dataset.section);
      btn.setAttribute("aria-expanded", "true");
      openModal(sectionModal, btn);
    });
  });
  document.addEventListener("keydown", (e) => {
    if (!activeModal) return;
    if (e.key === "Escape") {
      e.preventDefault();
      closeAllModals();
      return;
    }
    if (e.key !== "Tab") return;
    const focusable = focusableElements(activeModal);
    if (!focusable.length) {
      e.preventDefault();
      activeModal.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });

  function buildActionsBar(doc) {
    const bar = doc.createElement("div");
    bar.id = "vjpb-actions";
    bar.className = "vjpb-actions";
    bar.appendChild(makeActionButton(doc, "Editar", "✎", openEditorModal, false));
    bar.appendChild(makeActionButton(doc, "Duplicar", "⧉", () => clickParent("duplicateButton"), false));
    bar.appendChild(makeActionButton(doc, "Eliminar", "🗑", () => clickParent("deleteButton"), true));
    return bar;
  }

  // Click on empty preview space (outside any editable element or the action
  // bar) clears the selection. Bound once per fresh iframe document — srcdoc
  // reloads replace the document, so the poll re-binds via the dataset flag.
  function bindClickOutsideOnce(doc) {
    if (doc.body.dataset.vjpbClickOutsideBound) return;
    doc.body.dataset.vjpbClickOutsideBound = "1";
    doc.addEventListener("click", event => {
      const target = event.target;
      const onEditable = target && typeof target.closest === "function" && target.closest("[data-vjpb-path]");
      const onActionsBar = target && typeof target.closest === "function" && target.closest("#vjpb-actions");
      if (!onEditable && !onActionsBar) {
        global.EditorCore.clearSelection();
      }
    });
  }

  function syncSelectionActions() {
    const frame = document.getElementById("previewFrame");
    const doc = frame && frame.contentDocument;
    const win = frame && frame.contentWindow;
    if (!doc || !doc.body || !win) return;
    bindClickOutsideOnce(doc);
    const selected = doc.querySelector(".__vjpb-selected");
    let bar = doc.getElementById("vjpb-actions");
    if (!selected) {
      if (bar) bar.remove();
      return;
    }
    if (!doc.getElementById("vjpb-actions-style")) {
      const style = doc.createElement("style");
      style.id = "vjpb-actions-style";
      style.textContent = ACTION_STYLE;
      doc.head.appendChild(style);
    }
    if (!bar) {
      bar = buildActionsBar(doc);
      doc.body.appendChild(bar);
    }
    const rect = selected.getBoundingClientRect();
    bar.style.top = rect.top + win.scrollY + "px";
    bar.style.left = rect.right + win.scrollX + "px";
  }

  function onSelectionChange() {
    syncGlobalModeDefault();
    updateContextChip();
    syncSelectionActions();
  }

  function bindSelectionChangeOnce(doc) {
    if (!doc || !doc.body || doc.body.dataset.vjpbSelectionChangeBound) return;
    doc.body.dataset.vjpbSelectionChangeBound = "1";
    doc.addEventListener("vjpb:selection-change", onSelectionChange);
  }

  syncGlobalModeDefault();
  updateContextChip();
  const previewFrame = document.getElementById("previewFrame");
  if (previewFrame) {
    bindSelectionChangeOnce(previewFrame.contentDocument);
    // ponytail: srcdoc reload replaces contentDocument, dropping the listener —
    // rebind on load. add a scroll/resize listener for the action bar only if
    // that lag is ever felt.
    previewFrame.addEventListener("load", () => {
      bindSelectionChangeOnce(previewFrame.contentDocument);
      onSelectionChange();
    });
  }
})(typeof window !== "undefined" ? window : globalThis);
