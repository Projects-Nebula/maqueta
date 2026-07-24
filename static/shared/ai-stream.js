/* Shared SSE transport and live reasoning bubble for AI surfaces. */
(function (global) {
  "use strict";

  function looksLikeCode(text) {
    if (!text) return true;
    if (/^[{[]/.test(text)) return true;
    if (/"[a-zA-Z0-9_-]+"\s*:/.test(text)) return true;
    if (/<\/?[a-z][a-z0-9-]*(\s[^>]*)?>/i.test(text)) return true;
    return false;
  }

  function parseSseBlock(block) {
    let eventName = "message";
    const dataLines = [];
    block.split(/\r?\n/).forEach((line) => {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    });
    if (!dataLines.length) return null;
    try {
      return { event: eventName, data: JSON.parse(dataLines.join("\n")) };
    } catch {
      return null;
    }
  }

  async function consume(response, onReasoning) {
    if (!response.body || typeof response.body.getReader !== "function") {
      return { done: null, error: { error: "missing_stream" } };
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let reasoningSoFar = "";
    let doneEvent = null;
    let errorEvent = null;

    const processBlock = (block) => {
      const parsed = parseSseBlock(block);
      if (!parsed) return;
      if (parsed.event === "reasoning") {
        const text = parsed.data && typeof parsed.data.text === "string" ? parsed.data.text : "";
        reasoningSoFar += text;
        if (text && typeof onReasoning === "function") onReasoning(reasoningSoFar);
      } else if (parsed.event === "done") {
        doneEvent = parsed.data;
      } else if (parsed.event === "error") {
        errorEvent = parsed.data;
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let separatorIndex;
      while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
        processBlock(buffer.slice(0, separatorIndex));
        buffer = buffer.slice(separatorIndex + 2);
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) processBlock(buffer);
    return { done: doneEvent, error: errorEvent };
  }

  function createTypingBubble({ messages, scrollToBottom, statusMessages, ariaLabel }) {
    const doc = messages.ownerDocument || global.document;
    const wrap = doc.createElement("div");
    wrap.className = "ai-msg ai-msg-assistant ai-msg-typing";
    const bubble = doc.createElement("div");
    bubble.className = "ai-bubble ai-bubble-assistant ai-typing";
    bubble.setAttribute("aria-label", ariaLabel || "El asistente está trabajando");

    const dots = doc.createElement("span");
    dots.className = "ai-typing-dots";
    dots.appendChild(doc.createElement("span"));
    dots.appendChild(doc.createElement("span"));
    dots.appendChild(doc.createElement("span"));
    bubble.appendChild(dots);

    const status = doc.createElement("span");
    status.className = "ai-typing-status";
    status.textContent = statusMessages[0] || "Pensando…";
    bubble.appendChild(status);

    wrap.appendChild(bubble);
    messages.appendChild(wrap);
    scrollToBottom();

    let index = 0;
    let live = false;
    let shownSentenceCount = 0;
    const timer = setInterval(() => {
      if (live || !statusMessages.length) return;
      index = (index + 1) % statusMessages.length;
      status.textContent = statusMessages[index];
    }, 2200);

    function setReasoning(text) {
      if (!text) return;
      live = true;
      bubble.classList.add("ai-typing-live");
      status.classList.add("ai-typing-status-live");

      const sentences = [];
      let lastEnd = 0;
      let match;
      const sentencePattern = /\.\s*\n+/g;
      while ((match = sentencePattern.exec(text)) !== null) {
        sentences.push(text.slice(lastEnd, match.index + 1).trim());
        lastEnd = sentencePattern.lastIndex;
      }
      if (sentences.length <= shownSentenceCount) return;

      for (let i = sentences.length - 1; i >= shownSentenceCount; i -= 1) {
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

  global.AIStream = Object.freeze({ consume, createTypingBubble, parseSseBlock });
})(window);
