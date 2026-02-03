const MENU_ID = "gpt-explain-selection";
const SERVER_URL = "http://127.0.0.1:8787/explain";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: MENU_ID,
    title: "Ask GPT: what is \"%s\"",
    contexts: ["selection"]
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== MENU_ID || !info.selectionText) return;

  const selection = info.selectionText.trim();
  if (!selection) return;

  const prompt = `what is ${selection}`;

  try {
    const res = await fetch(SERVER_URL, {
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
