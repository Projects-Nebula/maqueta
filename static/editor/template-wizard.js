/* AI-guided "create a custom template from scratch" wizard.
 *
 * ponytail: shares its SSE-parsing/typing-bubble logic conceptually with
 * editor-ai.js but keeps its own copy instead of extracting a shared module —
 * that editor-ai.js code is working and already iterated on; refactoring it
 * to accept parameters risked regressing it for a same-day payoff. Revisit
 * if a third consumer shows up.
 */
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
  };
  if (!els.messages) return;

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

  const TYPING_STATUS_MESSAGES = [
    "Pensando…",
    "Analizando tu idea…",
    "Preparando la respuesta…",
  ];
  const TYPING_STATUS_INTERVAL_MS = 2200;
  const REASONING_SENTENCE_RE = /\.\s*\n+/g;

  function looksLikeCode(text) {
    if (!text) return true;
    if (/^[{[]/.test(text)) return true;
    if (/"[a-zA-Z0-9_-]+"\s*:/.test(text)) return true;
    if (/<\/?[a-z][a-z0-9-]*(\s[^>]*)?>/i.test(text)) return true;
    return false;
  }

  function appendTypingBubble() {
    const wrap = document.createElement("div");
    wrap.className = "ai-msg ai-msg-assistant ai-msg-typing";
    const bubble = document.createElement("div");
    bubble.className = "ai-bubble ai-bubble-assistant ai-typing";
    bubble.setAttribute("aria-label", "El asistente está trabajando");

    const dots = document.createElement("span");
    dots.className = "ai-typing-dots";
    dots.appendChild(document.createElement("span"));
    dots.appendChild(document.createElement("span"));
    dots.appendChild(document.createElement("span"));
    bubble.appendChild(dots);

    const status = document.createElement("span");
    status.className = "ai-typing-status";
    status.textContent = TYPING_STATUS_MESSAGES[0];
    bubble.appendChild(status);

    wrap.appendChild(bubble);
    els.messages.appendChild(wrap);
    scrollToBottom();

    let index = 0;
    let live = false;
    let shownSentenceCount = 0;
    const timer = setInterval(() => {
      if (live) return;
      index = (index + 1) % TYPING_STATUS_MESSAGES.length;
      status.textContent = TYPING_STATUS_MESSAGES[index];
    }, TYPING_STATUS_INTERVAL_MS);

    function setReasoning(text) {
      if (!text) return;
      live = true;
      bubble.classList.add("ai-typing-live");
      status.classList.add("ai-typing-status-live");

      const sentences = [];
      let lastEnd = 0;
      let match;
      REASONING_SENTENCE_RE.lastIndex = 0;
      while ((match = REASONING_SENTENCE_RE.exec(text)) !== null) {
        sentences.push(text.slice(lastEnd, match.index + 1).trim());
        lastEnd = REASONING_SENTENCE_RE.lastIndex;
      }
      if (sentences.length <= shownSentenceCount) return;

      for (let i = sentences.length - 1; i >= shownSentenceCount; i--) {
        if (!looksLikeCode(sentences[i])) {
          status.textContent = sentences[i];
          scrollToBottom();
          break;
        }
      }
      shownSentenceCount = sentences.length;
    }

    function remove() {
      clearInterval(timer);
      wrap.remove();
    }

    return { remove, setReasoning };
  }

  function parseSseBlock(block) {
    let eventName = "message";
    let dataLine = null;
    block.split("\n").forEach((line) => {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLine = line.slice(5).trim();
    });
    if (!dataLine) return null;
    try {
      return { event: eventName, data: JSON.parse(dataLine) };
    } catch (err) {
      return null;
    }
  }

  // Reads an SSE response, calling onReasoning(text) for each "reasoning"
  // chunk, and resolving with the terminal {done, error} event data.
  async function consumeStream(response, onReasoning) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let reasoningSoFar = "";
    let doneEvent = null;
    let errorEvent = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let separatorIndex;
      while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, separatorIndex);
        buffer = buffer.slice(separatorIndex + 2);
        const parsed = parseSseBlock(block);
        if (!parsed) continue;
        if (parsed.event === "reasoning") {
          reasoningSoFar += parsed.data.text;
          onReasoning(reasoningSoFar);
        } else if (parsed.event === "done") {
          doneEvent = parsed.data;
        } else if (parsed.event === "error") {
          errorEvent = parsed.data;
        }
      }
    }
    return { done: doneEvent, error: errorEvent };
  }

  function errorMessage(data) {
    const code = data && data.error;
    const map = {
      ai_timeout: "El asistente tardó demasiado. Intentá de nuevo.",
      ai_unavailable: "El asistente no está disponible ahora.",
      invalid_questions: "No se pudo armar el formulario. Reformulá tu descripción.",
      invalid_document: "No se pudo generar la página. Intentá de nuevo.",
      invalid_input: "Solicitud no válida.",
    };
    return map[code] || "Algo salió mal. Intentá de nuevo.";
  }

  async function postStream(url, body) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify(body),
    });
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("text/event-stream")) {
      const data = await response.json().catch(() => ({}));
      return { done: null, error: data.error ? data : { error: "invalid_input" } };
    }
    const typingBubble = appendTypingBubble();
    try {
      return await consumeStream(response, (text) => typingBubble.setReasoning(text));
    } finally {
      typingBubble.remove();
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
  };

  function renderImageList() {
    if (!els.imageList) return;
    els.imageList.innerHTML = "";
    state.assets.forEach((asset) => {
      const img = document.createElement("img");
      img.src = asset.url;
      img.alt = "";
      els.imageList.appendChild(img);
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
        id: "asset-" + data.id,
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
    const { done, error } = await postStream("/api/ai/wizard/questions/", {
      description: state.description,
      history: state.history,
    });
    if (error) {
      appendErrorBubble(errorMessage(error));
      return;
    }
    state.questions = done.questions;
    appendAssistantBubble("Armé estas preguntas para conocer mejor tu página:");
    renderQuestionForm(state.questions);
    state.phase = "questions";
  }

  async function requestReview() {
    const { done, error } = await postStream("/api/ai/wizard/review/", {
      description: state.description,
      answers: state.answers,
      history: state.history,
    });
    if (error) {
      appendErrorBubble(errorMessage(error));
      setComposerVisible(true);
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
    const { done, error } = await postStream("/api/ai/wizard/generate/", {
      description: state.description,
      answers: state.answers,
      history: state.history,
      assets: state.assets,
    });
    if (error) {
      appendErrorBubble(errorMessage(error));
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
    nameLabel.textContent = "Nombre del template";
    nameField.appendChild(nameLabel);
    const nameInput = document.createElement("input");
    nameInput.type = "text";
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
