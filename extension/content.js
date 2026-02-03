(function () {
  const CONTAINER_ID = "gpt-explain-container";

  function ensureContainer() {
    let el = document.getElementById(CONTAINER_ID);
    if (el) return el;

    el = document.createElement("div");
    el.id = CONTAINER_ID;
    el.innerHTML = `
      <div class="gpt-explain-header">
        <div class="gpt-explain-title">GPT Explain</div>
        <button class="gpt-explain-close" title="Close">×</button>
      </div>
      <div class="gpt-explain-body"></div>
    `;

    document.documentElement.appendChild(el);

    el.querySelector(".gpt-explain-close").addEventListener("click", () => {
      el.remove();
    });

    return el;
  }

  function setBody(content, isError) {
    const el = ensureContainer();
    const body = el.querySelector(".gpt-explain-body");
    if (isError) {
      body.textContent = content;
    } else {
      body.innerHTML = formatAnswer(content);
    }
    if (isError) {
      el.classList.add("gpt-explain-error");
    } else {
      el.classList.remove("gpt-explain-error");
    }
  }

  function formatAnswer(raw) {
    if (!raw) return "";
    let text = String(raw).replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    text = stripSelectionLine(text);

    const paragraphs = text
      .split(/\n\s*\n+/)
      .map((p) => p.replace(/\s*\n\s*/g, " ").trim())
      .filter(Boolean);

    if (paragraphs.length === 0) return "";

    return paragraphs.map((p) => `<p>${escapeHtml(p)}</p>`).join("");
  }

  function stripSelectionLine(text) {
    const lines = text.split("\n");
    const filtered = lines.filter((line) => {
      const trimmed = line.trim();
      if (!trimmed) return true;
      return !/^(selected|selection|输入)\s*[:：]/i.test(trimmed);
    });
    return filtered.join("\n");
  }

  function escapeHtml(value) {
    return value
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type === "GPT_EXPLAIN_RESULT") {
      setBody(msg.answer, false);
    }

    if (msg?.type === "GPT_EXPLAIN_ERROR") {
      setBody(`Error: ${msg.error}`, true);
    }
  });
})();
