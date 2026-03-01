const API = 'https://api.dejaview.io';

// Context menu — right-click any selected text
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

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'dv-save') {
    // Open popup with selected text pre-filled
    await chrome.storage.session.set({ prefill: info.selectionText });
    await chrome.action.openPopup();
  }
  if (info.menuItemId === 'dv-extract') {
    // Inject extraction into the tab
    chrome.tabs.sendMessage(tab.id, { type: 'EXTRACT', selection: info.selectionText || '' });
  }
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'API_CALL') {
    apiCall(msg.method, msg.path, msg.body)
      .then(data => sendResponse({ ok: true, data }))
      .catch(err => sendResponse({ ok: false, error: err.message }));
    return true; // keep channel open for async
  }
});

async function apiCall(method, path, body) {
  const { apiKey } = await chrome.storage.sync.get('apiKey');
  if (!apiKey) throw new Error('No API key set — open DejaView extension to configure.');
  const opts = {
    method,
    headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
