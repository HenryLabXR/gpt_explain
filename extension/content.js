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
    body.textContent = content;
    if (isError) {
      el.classList.add("gpt-explain-error");
    } else {
      el.classList.remove("gpt-explain-error");
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
})();
