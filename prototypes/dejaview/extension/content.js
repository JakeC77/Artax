// DejaView content script — handles extraction panel

let panel = null;

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'EXTRACT') {
    const text = msg.selection || extractPageText();
    showExtractionPanel(text);
  }
});

function extractPageText() {
  // Grab the most meaningful text from the page
  const article = document.querySelector('article, main, [role="main"], .post-content, .entry-content');
  const el = article || document.body;
  return el.innerText.slice(0, 4000).trim();
}

function showExtractionPanel(text) {
  if (panel) panel.remove();

  panel = document.createElement('div');
  panel.id = 'dv-panel';
  panel.innerHTML = `
    <div id="dv-header">
      <span>🔮 DejaView</span>
      <button id="dv-close">✕</button>
    </div>
    <div id="dv-body">
      <div id="dv-status">Extracting facts from this page...</div>
      <div id="dv-facts"></div>
      <div id="dv-actions" style="display:none">
        <button id="dv-save-all">Save all</button>
        <button id="dv-dismiss">Dismiss</button>
      </div>
    </div>
  `;

  const style = document.createElement('style');
  style.textContent = `
    #dv-panel{position:fixed;bottom:24px;right:24px;width:340px;max-height:480px;background:#111827;border:1px solid rgba(124,92,252,.4);border-radius:14px;box-shadow:0 8px 40px rgba(0,0,0,.6);z-index:2147483647;font-family:system-ui,sans-serif;color:#e4e4ef;overflow:hidden;display:flex;flex-direction:column}
    #dv-header{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid rgba(255,255,255,.07);font-weight:700;font-size:.9rem;background:#0a0e17;flex-shrink:0}
    #dv-close{background:none;border:none;color:#9494a8;cursor:pointer;font-size:1rem;padding:2px 6px;border-radius:4px}
    #dv-close:hover{background:rgba(255,255,255,.1)}
    #dv-body{padding:14px;overflow-y:auto;flex:1}
    #dv-status{color:#9494a8;font-size:.85rem;margin-bottom:10px}
    .dv-fact{background:#1a2035;border:1px solid rgba(255,255,255,.07);border-radius:8px;padding:10px 12px;margin-bottom:8px;font-size:.82rem;cursor:pointer;transition:border-color .2s;display:flex;align-items:center;gap:10px}
    .dv-fact:hover{border-color:rgba(124,92,252,.4)}
    .dv-fact.selected{border-color:#7c5cfc;background:rgba(124,92,252,.12)}
    .dv-fact-text{flex:1;line-height:1.5}
    .dv-fact-text strong{color:#a78bfa}
    .dv-check{width:16px;height:16px;border:2px solid rgba(255,255,255,.2);border-radius:4px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:.7rem}
    .dv-fact.selected .dv-check{background:#7c5cfc;border-color:#7c5cfc}
    #dv-actions{display:flex;gap:8px;margin-top:12px}
    #dv-save-all{flex:1;background:#7c5cfc;color:#fff;border:none;border-radius:8px;padding:9px;font-weight:600;font-size:.83rem;cursor:pointer;font-family:inherit}
    #dv-save-all:hover{background:#6a4de0}
    #dv-dismiss{background:rgba(255,255,255,.05);color:#9494a8;border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:9px 14px;font-size:.83rem;cursor:pointer;font-family:inherit}
  `;
  document.head.appendChild(style);
  document.body.appendChild(panel);

  document.getElementById('dv-close').onclick = () => panel.remove();
  document.getElementById('dv-dismiss')?.addEventListener('click', () => panel.remove());

  // Ask background to call /v1/extract
  chrome.runtime.sendMessage({
    type: 'API_CALL',
    method: 'POST',
    path: '/v1/extract',
    body: { text, url: location.href, title: document.title },
  }, (resp) => {
    const statusEl = document.getElementById('dv-status');
    const factsEl = document.getElementById('dv-facts');
    const actionsEl = document.getElementById('dv-actions');

    if (!resp || !resp.ok) {
      statusEl.textContent = resp?.error || 'Extraction failed.';
      return;
    }

    const facts = resp.data.facts || [];
    if (!facts.length) {
      statusEl.textContent = 'No facts extracted from this page.';
      return;
    }

    statusEl.textContent = `Found ${facts.length} fact${facts.length !== 1 ? 's' : ''} — tap to select:`;

    facts.forEach((f, i) => {
      const div = document.createElement('div');
      div.className = 'dv-fact selected';
      div.dataset.idx = i;
      div.innerHTML = `
        <div class="dv-check">✓</div>
        <div class="dv-fact-text">
          <strong>${esc(f.subject)}</strong>
          <span style="color:#6a6a80"> ${esc(f.predicate)} </span>
          <strong>${esc(f.object)}</strong>
        </div>`;
      div.onclick = () => {
        div.classList.toggle('selected');
        div.querySelector('.dv-check').textContent = div.classList.contains('selected') ? '✓' : '';
      };
      factsEl.appendChild(div);
    });

    actionsEl.style.display = 'flex';

    document.getElementById('dv-save-all').onclick = () => {
      const selected = [...document.querySelectorAll('.dv-fact.selected')].map(el => facts[+el.dataset.idx]);
      if (!selected.length) return;
      chrome.runtime.sendMessage({
        type: 'API_CALL', method: 'POST', path: '/v1/facts',
        body: { facts: selected },
      }, (r) => {
        if (r?.ok) {
          statusEl.textContent = `✅ Saved ${r.data.stored} fact${r.data.stored !== 1 ? 's' : ''}!`;
          actionsEl.style.display = 'none';
          factsEl.querySelectorAll('.dv-fact').forEach(el => el.style.opacity = '.4');
          setTimeout(() => panel?.remove(), 2000);
        } else {
          statusEl.textContent = 'Save failed: ' + (r?.error || 'unknown error');
        }
      });
    };
  });
}

function esc(s) { return String(s).replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
