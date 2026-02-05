const MENU_EXPLAIN_ID = "gpt-explain-selection";
const MENU_TRANSLATE_ID = "gpt-translate-selection";
const SERVER_BASE = "http://127.0.0.1:8787";
const EXPLAIN_URL = `${SERVER_BASE}/explain`;
const TRANSLATE_URL = `${SERVER_BASE}/translate`;

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: MENU_EXPLAIN_ID,
    title: "Ask GPT: what is \"%s\"",
    contexts: ["selection"]
  });
  chrome.contextMenus.create({
    id: MENU_TRANSLATE_ID,
    title: "Ask GPT: translate \"%s\"",
    contexts: ["selection"]
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!info.selectionText) return;

  const selection = info.selectionText.trim();
  if (!selection) return;

  const isExplain = info.menuItemId === MENU_EXPLAIN_ID;
  const isTranslate = info.menuItemId === MENU_TRANSLATE_ID;
  if (!isExplain && !isTranslate) return;

  const isLongText = selection.length >= 120 || selection.includes("\n");
  const prompt = isExplain && !isLongText ? `what is ${selection}` : "";
  const url = isExplain ? EXPLAIN_URL : TRANSLATE_URL;

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: selection, prompt })
    });

    const data = await res.json();
    if (!res.ok || !data.ok) {
      throw new Error(data.error || "Request failed");
    }

    if (tab?.id) {
      chrome.tabs.sendMessage(tab.id, {
        type: "GPT_EXPLAIN_RESULT",
        selection,
        answer: data.text
      });
    }
  } catch (err) {
    const message = err?.message || "Unknown error";
    if (tab?.id) {
      chrome.tabs.sendMessage(tab.id, {
        type: "GPT_EXPLAIN_ERROR",
        selection,
        error: message
      });
    }
  }
});
