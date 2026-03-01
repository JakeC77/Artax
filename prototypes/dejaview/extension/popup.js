const API_DEFAULT = 'https://api.dejaview.io';

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('pane-' + tab.dataset.tab).classList.add('active');
  });
});

// Load saved settings
chrome.storage.sync.get(['apiKey', 'endpoint'], ({ apiKey, endpoint }) => {
  if (apiKey) {
    document.getElementById('s-key').value = apiKey;
    document.getElementById('conn-badge').style.display = 'inline';
  }
  document.getElementById('s-endpoint').value = endpoint || API_DEFAULT;
});

// Pre-fill from context menu selection
chrome.storage.session.get('prefill', ({ prefill }) => {
  if (prefill) {
    document.getElementById('f-subject').value = prefill.trim();
    document.querySelector('[data-tab="remember"]').click();
    chrome.storage.session.remove('prefill');
  }
});

// Save settings
document.getElementById('save-settings').addEventListener('click', () => {
  const key = document.getElementById('s-key').value.trim();
  const endpoint = document.getElementById('s-endpoint').value.trim() || API_DEFAULT;
  chrome.storage.sync.set({ apiKey: key, endpoint }, () => {
    showMsg('settings-msg', 'Saved!', 'success');
    if (key) document.getElementById('conn-badge').style.display = 'inline';
  });
});

// Test connection
document.getElementById('test-conn').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'API_CALL', method: 'GET', path: '/v1/health' }, (resp) => {
    if (resp?.ok) {
      showMsg('settings-msg', 'Connected ✓', 'success');
    } else {
      showMsg('settings-msg', resp?.error || 'Connection failed', 'error');
    }
  });
});

// Save single fact
document.getElementById('save-btn').addEventListener('click', () => {
  const subject   = document.getElementById('f-subject').value.trim();
  const predicate = document.getElementById('f-predicate').value.trim();
  const object    = document.getElementById('f-object').value.trim();
  const context   = document.getElementById('f-context').value.trim();

  if (!subject || !predicate || !object) {
    showMsg('save-msg', 'Subject, predicate, and object are required.', 'error');
    return;
  }

  const fact = { subject, predicate, object };
  if (context) fact.context = context;
  fact.source = 'browser-extension';

  const btn = document.getElementById('save-btn');
  btn.disabled = true;
  btn.textContent = 'Saving...';

  chrome.runtime.sendMessage({
    type: 'API_CALL', method: 'POST', path: '/v1/facts',
    body: { facts: [fact] },
  }, (resp) => {
    btn.disabled = false;
    btn.textContent = 'Save fact';
    if (resp?.ok && resp.data.stored) {
      showMsg('save-msg', `Saved: ${subject} → ${predicate} → ${object}`, 'success');
      document.getElementById('f-subject').value = '';
      document.getElementById('f-predicate').value = '';
      document.getElementById('f-object').value = '';
      document.getElementById('f-context').value = '';
    } else {
      showMsg('save-msg', resp?.error || 'Save failed', 'error');
    }
  });
});

// Extract from page
document.getElementById('extract-btn').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.tabs.sendMessage(tab.id, { type: 'EXTRACT', selection: '' });
  window.close(); // close popup, panel will appear on page
});

function showMsg(id, text, type) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = 'msg ' + type;
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 3000);
}
