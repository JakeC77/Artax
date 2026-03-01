const API = 'https://api.dejaview.io';

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'dv-save',
    title: 'Save to DejaView',
    contexts: ['selection'],
  });
  chrome.contextMenus.create({
    id: 'dv-extract',
    title: 'Extract facts from this page',
    contexts: ['page', 'selection'],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'dv-save') {
    // Show inline quick-save panel with selected text pre-filled
    chrome.tabs.sendMessage(tab.id, {
      type: 'QUICK_SAVE',
      selection: info.selectionText || '',
    });
  }
  if (info.menuItemId === 'dv-extract') {
    chrome.tabs.sendMessage(tab.id, {
      type: 'EXTRACT',
      selection: info.selectionText || '',
    });
  }
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'API_CALL') {
    apiCall(msg.method, msg.path, msg.body)
      .then(data => sendResponse({ ok: true, data }))
      .catch(err => sendResponse({ ok: false, error: err.message }));
    return true;
  }
});

async function apiCall(method, path, body) {
  const { apiKey } = await chrome.storage.sync.get('apiKey');
  if (!apiKey) throw new Error('No API key — click the DejaView icon to set one.');
  const opts = {
    method,
    headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  if (!r.ok) {
    const text = await r.text().catch(() => r.statusText);
    throw new Error(`${r.status}: ${text}`);
  }
  return r.json();
}
