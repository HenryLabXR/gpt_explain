(function () {
  const CONTAINER_ID = "gpt-explain-container";
  const TOOLBAR_ID = "gpt-explain-toolbar";
  const SERVER_BASE = "http://127.0.0.1:8787";
  const EXPLAIN_URL = `${SERVER_BASE}/explain`;
  const TRANSLATE_URL = `${SERVER_BASE}/translate`;
  let lastSelection = "";

  function ensureContainer() {
    let el = document.getElementById(CONTAINER_ID);
    if (el) return el;

    el = document.createElement("div");
    el.id = CONTAINER_ID;
    el.innerHTML = `
      <div class="gpt-explain-header">
        <div class="gpt-explain-title">GPT Explain</div>
        <div class="gpt-explain-actions">
          <button class="gpt-explain-btn" data-action="explain">Explain</button>
          <button class="gpt-explain-btn" data-action="translate">Translate</button>
        </div>
        <button class="gpt-explain-close" title="Close">×</button>
      </div>
      <div class="gpt-explain-body"></div>
    `;

    document.documentElement.appendChild(el);

    el.querySelector(".gpt-explain-close").addEventListener("click", () => {
      el.remove();
    });

    el.querySelectorAll(".gpt-explain-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (!lastSelection) {
          setBody("No selection to process.", true);
          return;
        }
        const action = btn.getAttribute("data-action");
        if (action === "explain") {
          requestExplain(lastSelection);
        } else {
          requestTranslate(lastSelection);
        }
      });
    });

    return el;
  }

  function ensureToolbar() {
    let el = document.getElementById(TOOLBAR_ID);
    if (el) return el;

    el = document.createElement("div");
    el.id = TOOLBAR_ID;
    el.innerHTML = `
      <button class="gpt-explain-btn" data-action="explain">Explain</button>
      <button class="gpt-explain-btn" data-action="translate">Translate</button>
    `;
    document.documentElement.appendChild(el);

    el.querySelectorAll(".gpt-explain-btn").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        if (!lastSelection) return;
        const action = btn.getAttribute("data-action");
        if (action === "explain") {
          requestExplain(lastSelection);
        } else {
          requestTranslate(lastSelection);
        }
        hideToolbar();
      });
    });

    return el;
  }

  function showToolbar(rect) {
    const el = ensureToolbar();
    const padding = 8;
    const top = Math.min(
      window.scrollY + rect.bottom + padding,
      window.scrollY + window.innerHeight - 40
    );
    const left = Math.min(
      window.scrollX + rect.left,
      window.scrollX + window.innerWidth - 140
    );
    el.style.top = `${top}px`;
    el.style.left = `${left}px`;
    el.style.display = "flex";
  }

  function hideToolbar() {
    const el = document.getElementById(TOOLBAR_ID);
    if (el) el.style.display = "none";
  }

  function updateSelection() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) {
      lastSelection = "";
      hideToolbar();
      return;
    }

    const text = sel.toString().trim();
    if (!text) {
      lastSelection = "";
      hideToolbar();
      return;
    }

    lastSelection = text;
    const range = sel.rangeCount ? sel.getRangeAt(0) : null;
    if (!range) return;
    const rect = range.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) {
      hideToolbar();
      return;
    }
    showToolbar(rect);
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

    const hasBlankLines = /\n\s*\n/.test(text);
    if (!hasBlankLines && text.includes("\n")) {
      const lines = text
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => escapeHtml(line));
      return lines.join("<br>");
    }

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

  async function postRequest(url, text, prompt) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, prompt })
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      throw new Error(data.error || "Request failed");
    }
    return data;
  }

  async function requestExplain(selection) {
    const isLongText = selection.length >= 120 || selection.includes("\n");
    const prompt = isLongText ? "" : `what is ${selection}`;
    setBody("Loading...", false);
    try {
      const data = await postRequest(EXPLAIN_URL, selection, prompt);
      setBody(data.text, false);
    } catch (err) {
      setBody(`Error: ${err?.message || "Unknown error"}`, true);
    }
  }

  async function requestTranslate(selection) {
    setBody("Loading...", false);
    try {
      const data = await postRequest(TRANSLATE_URL, selection, "");
      setBody(data.text, false);
    } catch (err) {
      setBody(`Error: ${err?.message || "Unknown error"}`, true);
    }
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type === "GPT_EXPLAIN_RESULT") {
      setBody(msg.answer, false);
    }

    if (msg?.type === "GPT_EXPLAIN_ERROR") {
      setBody(`Error: ${msg.error}`, true);
    }
  });

  document.addEventListener("mouseup", () => {
    setTimeout(updateSelection, 0);
  });

  document.addEventListener("keyup", (e) => {
    if (e.key === "Shift" || e.key === "Control" || e.key === "Alt") return;
    setTimeout(updateSelection, 0);
  });

  document.addEventListener("scroll", hideToolbar, true);
})();
