/* AI-guided "create a custom template from scratch" wizard. */
(function () {
  "use strict";

  const els = {
    messages: document.getElementById("wizardMessages"),
    composer: document.getElementById("wizardComposer"),
    input: document.getElementById("wizardInput"),
    send: document.getElementById("wizardSend"),
    form: document.getElementById("wizardQuestionForm"),
    fields: document.getElementById("wizardFields"),
    imageInput: document.getElementById("wizardImageInput"),
    imageList: document.getElementById("wizardImageList"),
    cancel: document.getElementById("wizardCancel"),
    restart: document.getElementById("wizardRestart"),
    requestMessage: document.getElementById("wizardRequestMessage"),
    paletteSelect: document.getElementById("wizardPaletteSelect"),
    palettePreview: document.getElementById("wizardPalettePreview"),
  };
  if (!els.messages) return;

  function readPaletteCatalog() {
    const element = document.getElementById("palette-catalog");
    if (!element) return { roles: [], presets: [], user_palettes: [] };
    try {
      const parsed = JSON.parse(element.textContent || "{}");
      return {
        roles: Array.isArray(parsed.roles) ? parsed.roles : [],
        presets: Array.isArray(parsed.presets) ? parsed.presets : [],
        user_palettes: Array.isArray(parsed.user_palettes) ? parsed.user_palettes : [],
      };
    } catch {
      return { roles: [], presets: [], user_palettes: [] };
    }
  }

  const paletteCatalog = readPaletteCatalog();

  const MAX_ASSETS = 20;

  const MAX_REVIEW_ROUNDS = 5;

  function getCsrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function scrollToBottom() {
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function appendUserBubble(text) {
    const wrap = document.createElement("div");
    wrap.className = "ai-msg ai-msg-user";
    const bubble = document.createElement("div");
    bubble.className = "ai-bubble";
    bubble.textContent = text;
    wrap.appendChild(bubble);
    els.messages.appendChild(wrap);
    scrollToBottom();
  }

  function appendAssistantBubble(text) {
    const wrap = document.createElement("div");
    wrap.className = "ai-msg ai-msg-assistant";
    const bubble = document.createElement("div");
    bubble.className = "ai-bubble ai-bubble-assistant";
    bubble.textContent = text;
    wrap.appendChild(bubble);
    els.messages.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function appendErrorBubble(message) {
    const wrap = document.createElement("div");
    wrap.className = "ai-msg ai-msg-assistant";
    const bubble = document.createElement("div");
    bubble.className = "ai-bubble ai-bubble-error";
    bubble.textContent = message;
    wrap.appendChild(bubble);
    els.messages.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  let activeRequestController = null;

  function setRequestState(isBusy, message) {
    if (els.requestMessage) els.requestMessage.textContent = isBusy ? message : "";
    if (els.cancel) els.cancel.classList.toggle("hidden", !isBusy);
    if (els.send) els.send.disabled = isBusy;
  }

  function appendTypingBubble() {
    return window.AIStream.createTypingBubble({
      messages: els.messages,
      scrollToBottom,
      statusMessages: [
        "Pensando…",
        "Analizando tu idea…",
        "Preparando la respuesta…",
      ],
    });
  }

  function errorMessage(data) {
    const code = data && data.error;
    const map = {
      ai_timeout: "El asistente tardó demasiado. Intentá de nuevo.",
      ai_unavailable: "El asistente no está disponible ahora.",
      invalid_questions: "No se pudo armar el formulario. Reformulá tu descripción.",
      invalid_document: "No se pudo generar la página. Intentá de nuevo.",
      invalid_input: "Solicitud no válida.",
      network_error: "No se pudo conectar con el asistente. Revisá tu conexión e intentá de nuevo.",
    };
    return map[code] || "Algo salió mal. Intentá de nuevo.";
  }

  async function postStream(url, body) {
    const controller = new AbortController();
    activeRequestController = controller;
    setRequestState(true, "El asistente está trabajando…");
    try {
      const response = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("text/event-stream")) {
        const data = await response.json().catch(() => ({}));
        return { done: null, error: data.error ? data : { error: "invalid_input" } };
      }
      const typingBubble = appendTypingBubble();
      try {
        return await window.AIStream.consume(response, (text) => typingBubble.setReasoning(text));
      } finally {
        typingBubble.remove();
      }
    } catch (error) {
      if (error.name === "AbortError") return { cancelled: true };
      return { done: null, error: { error: "network_error" } };
    } finally {
      if (activeRequestController === controller) activeRequestController = null;
      setRequestState(false, "");
    }
  }

  // --- Wizard state & flow ---------------------------------------------------

  const state = {
    description: "",
    questions: [],
    answers: {},
    history: [],
    reviewRounds: 0,
    phase: "intro",
    assets: [],
    paletteId: "",
  };

  function renderPalettePreview() {
    if (!els.paletteSelect || !els.palettePreview) return;
    const palette = [...paletteCatalog.presets, ...paletteCatalog.user_palettes].find(
      (item) => item.id === state.paletteId,
    );
    els.palettePreview.replaceChildren();
    if (!palette) {
      els.palettePreview.textContent = "Sin selección: el asistente propondrá una paleta según tu descripción.";
      return;
    }
    const copy = document.createElement("span");
    copy.textContent = palette.description;
    els.palettePreview.appendChild(copy);
    const swatches = document.createElement("span");
    swatches.className = "wizard-palette-swatches";
    paletteCatalog.roles.forEach((role) => {
      const swatch = document.createElement("span");
      swatch.className = "wizard-palette-swatch";
      const value = palette.variables[role.variable];
      if (/^#[0-9a-f]{6}$/i.test(value || "")) swatch.style.backgroundColor = value;
      swatch.title = role.label + " " + (value || "");
      swatches.appendChild(swatch);
    });
    els.palettePreview.appendChild(swatches);
  }

  if (els.paletteSelect) {
    paletteCatalog.presets.forEach((preset) => {
      const option = document.createElement("option");
      option.value = preset.id;
      option.textContent = preset.name;
      els.paletteSelect.appendChild(option);
    });
    if (paletteCatalog.user_palettes.length) {
      const group = document.createElement("optgroup");
      group.label = "Mis paletas";
      paletteCatalog.user_palettes.forEach((palette) => {
        const option = document.createElement("option");
        option.value = palette.id;
        option.textContent = palette.name;
        group.appendChild(option);
      });
      els.paletteSelect.appendChild(group);
    }
    els.paletteSelect.addEventListener("change", () => {
      state.paletteId = els.paletteSelect.value;
      renderPalettePreview();
    });
    renderPalettePreview();
  }

  function renderImageList() {
    if (!els.imageList) return;
    els.imageList.innerHTML = "";
    state.assets.forEach((asset, index) => {
      const item = document.createElement("div");
      item.className = "wizard-image-item";
      const img = document.createElement("img");
      img.src = asset.url;
      img.alt = "Imagen cargada " + (index + 1);
      item.appendChild(img);

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "wizard-image-remove";
      removeButton.setAttribute("aria-label", "Quitar imagen " + (index + 1));
      removeButton.textContent = "×";
      removeButton.addEventListener("click", async () => {
        removeButton.disabled = true;
        try {
          const response = await fetch(
            "/api/user-templates/wizard-images/" + encodeURIComponent(asset.id) + "/",
            {
              method: "DELETE",
              credentials: "same-origin",
              headers: { "X-CSRFToken": getCsrfToken() },
            },
          );
          if (!response.ok) throw new Error("delete failed");
          state.assets.splice(index, 1);
          renderImageList();
        } catch (error) {
          removeButton.disabled = false;
          appendErrorBubble("No se pudo quitar la imagen. Intentá de nuevo.");
        }
      });
      item.appendChild(removeButton);
      els.imageList.appendChild(item);
    });
  }

  async function uploadImage(file) {
    if (state.assets.length >= MAX_ASSETS) {
      appendErrorBubble("Ya subiste el máximo de imágenes para este template.");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch("/api/user-templates/wizard-images/", {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": getCsrfToken() },
        body: formData,
      });
      if (!response.ok) {
        appendErrorBubble("No se pudo subir la imagen.");
        return;
      }
      const data = await response.json();
      state.assets.push({
        id: data.id,
        url: data.url,
        width: data.width,
        height: data.height,
      });
      renderImageList();
    } catch (e) {
      appendErrorBubble("No se pudo subir la imagen.");
    }
  }

  if (els.imageInput) {
    els.imageInput.addEventListener("change", () => {
      const file = els.imageInput.files && els.imageInput.files[0];
      if (file) uploadImage(file);
      els.imageInput.value = "";
    });
  }

  function setComposerVisible(visible) {
    els.composer.classList.toggle("hidden", !visible);
  }

  function setFormVisible(visible) {
    els.form.classList.toggle("hidden", !visible);
  }

  function renderQuestionForm(questions) {
    els.fields.innerHTML = "";
    questions.forEach((q) => {
      const field = document.createElement("div");
      field.className = "wizard-field";

      const label = document.createElement("label");
      label.textContent = q.label;
      label.setAttribute("for", "wizard-field-" + q.id);
      field.appendChild(label);

      let control;
      if (q.type === "select" && Array.isArray(q.options) && q.options.length) {
        control = document.createElement("select");
        q.options.forEach((opt) => {
          const optionEl = document.createElement("option");
          optionEl.value = opt;
          optionEl.textContent = opt;
          control.appendChild(optionEl);
        });
      } else if (q.type === "textarea") {
        control = document.createElement("textarea");
      } else {
        control = document.createElement("input");
        control.type = "text";
      }
      control.id = "wizard-field-" + q.id;
      control.dataset.questionId = q.id;
      if (q.required) control.required = true;
      if (q.placeholder) control.placeholder = q.placeholder;
      field.appendChild(control);

      els.fields.appendChild(field);
    });
    setFormVisible(true);
    setComposerVisible(false);
  }

  async function requestQuestions() {
    appendUserBubble(state.description);
    const result = await postStream("/api/ai/wizard/questions/", {
      description: state.description,
      history: state.history,
    });
    if (result.cancelled) return;
    const { done, error } = result;
    if (error || !done) {
      appendErrorBubble(errorMessage(error));
      state.phase = "intro";
      setComposerVisible(true);
      els.input.focus();
      return;
    }
    state.questions = done.questions;
    appendAssistantBubble("Armé estas preguntas para conocer mejor tu página:");
    renderQuestionForm(state.questions);
    state.phase = "questions";
  }

  async function requestReview() {
    const result = await postStream("/api/ai/wizard/review/", {
      description: state.description,
      answers: state.answers,
      history: state.history,
    });
    if (result.cancelled) return;
    const { done, error } = result;
    if (error || !done) {
      appendErrorBubble(errorMessage(error));
      state.phase = "clarifying";
      setComposerVisible(true);
      els.input.focus();
      return;
    }
    state.reviewRounds += 1;
    if (done.ready || state.reviewRounds >= MAX_REVIEW_ROUNDS) {
      await requestGenerate();
      return;
    }
    appendAssistantBubble(done.clarification);
    state.history.push({ role: "assistant", content: done.clarification });
    state.phase = "clarifying";
    setComposerVisible(true);
    els.input.focus();
  }

  async function requestGenerate() {
    state.phase = "generating";
    appendAssistantBubble("¡Listo! Generando tu página…");
    const result = await postStream("/api/ai/wizard/generate/", {
      description: state.description,
      answers: state.answers,
      history: state.history,
      assets: state.assets,
      palette_id: state.paletteId || null,
    });
    if (result.cancelled) return;
    const { done, error } = result;
    if (error || !done) {
      appendErrorBubble(errorMessage(error));
      state.phase = "clarifying";
      setComposerVisible(true);
      els.input.focus();
      return;
    }
    renderSaveStep(done.name, done.summary, done.state);
  }

  function renderSaveStep(name, summary, generatedState) {
    const wrap = document.createElement("div");
    wrap.className = "ai-msg ai-msg-assistant";
    const bubble = document.createElement("div");
    bubble.className = "ai-bubble ai-bubble-assistant";

    const summaryEl = document.createElement("p");
    summaryEl.className = "ai-bubble-summary";
    summaryEl.textContent = summary || "Tu página está lista.";
    bubble.appendChild(summaryEl);

    const nameField = document.createElement("div");
    nameField.className = "wizard-field";
    const nameLabel = document.createElement("label");
    nameLabel.setAttribute("for", "wizard-template-name");
    nameLabel.textContent = "Nombre del template";
    nameField.appendChild(nameLabel);
    const nameInput = document.createElement("input");
    nameInput.id = "wizard-template-name";
    nameInput.type = "text";
    nameInput.autocomplete = "off";
    nameInput.value = name || "Mi template";
    nameField.appendChild(nameInput);
    bubble.appendChild(nameField);

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "btn primary";
    saveBtn.textContent = "Guardar en mi galería";
    saveBtn.style.marginTop = "10px";
    bubble.appendChild(saveBtn);

    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      saveBtn.textContent = "Guardando…";
      try {
        const response = await fetch("/api/user-templates/", {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({ name: nameInput.value.trim() || "Mi template", state: generatedState }),
        });
        if (!response.ok) {
          throw new Error("save failed");
        }
        window.location.href = "/gallery/";
      } catch (err) {
        saveBtn.disabled = false;
        saveBtn.textContent = "Guardar en mi galería";
        appendErrorBubble("No se pudo guardar el template. Intentá de nuevo.");
      }
    });

    wrap.appendChild(bubble);
    els.messages.appendChild(wrap);
    scrollToBottom();
  }

  function collectAnswers() {
    const answers = {};
    els.fields.querySelectorAll("[data-question-id]").forEach((control) => {
      answers[control.dataset.questionId] = control.value;
    });
    return answers;
  }

  els.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!els.form.reportValidity()) return;
    state.answers = collectAnswers();
    setFormVisible(false);
    appendUserBubble("Respondí el formulario.");
    state.phase = "reviewing";
    await requestReview();
  });

  async function handleComposerSend() {
    const text = els.input.value.trim();
    if (!text) return;
    els.input.value = "";
    els.input.style.height = "auto";

    if (state.phase === "intro") {
      state.description = text;
      setComposerVisible(false);
      await requestQuestions();
      return;
    }

    if (state.phase === "clarifying") {
      appendUserBubble(text);
      state.history.push({ role: "user", content: text });
      setComposerVisible(false);
      await requestReview();
      return;
    }
  }

  els.send.addEventListener("click", handleComposerSend);
  els.cancel.addEventListener("click", () => {
    if (!activeRequestController) return;
    activeRequestController.abort();
    state.phase = state.description ? "clarifying" : "intro";
    setComposerVisible(true);
    setFormVisible(false);
    appendAssistantBubble("Cancelé la solicitud. Podés ajustar la idea y volver a intentarlo.");
    els.input.focus();
  });
  els.restart.addEventListener("click", () => {
    if (activeRequestController) activeRequestController.abort();
    state.description = "";
    state.questions = [];
    state.answers = {};
    state.history = [];
    state.reviewRounds = 0;
    state.phase = "intro";
    state.assets = [];
    state.paletteId = "";
    els.messages.innerHTML = "";
    els.fields.innerHTML = "";
    renderImageList();
    setRequestState(false, "");
    setFormVisible(false);
    setComposerVisible(true);
    els.input.value = "";
    els.input.style.height = "auto";
    if (els.paletteSelect) els.paletteSelect.value = "";
    renderPalettePreview();
    appendAssistantBubble("¿Qué página querés crear? Contame en tus palabras qué necesitás.");
    els.input.focus();
  });
  els.input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleComposerSend();
    }
  });
  els.input.addEventListener("input", () => {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(els.input.scrollHeight, 120) + "px";
  });

  appendAssistantBubble("¿Qué página querés crear? Contame en tus palabras qué necesitás.");
})();
