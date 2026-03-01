// DejaView content script

let panel = null;
let styleInjected = false;

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'EXTRACT') showExtractionPanel(msg.selection || extractPageText());
  if (msg.type === 'QUICK_SAVE') showQuickSave(msg.selection || '');
});

function extractPageText() {
  const el = document.querySelector('article, main, [role="main"], .post-content, .entry-content') || document.body;
  return el.innerText.slice(0, 4000).trim();
}

function injectStyles() {
  if (styleInjected) return;
  styleInjected = true;
  const s = document.createElement('style');
  s.textContent = `
    .dv-panel{position:fixed;bottom:24px;right:24px;width:340px;background:#111827;border:1px solid rgba(124,92,252,.4);border-radius:14px;box-shadow:0 8px 40px rgba(0,0,0,.6);z-index:2147483647;font-family:system-ui,sans-serif;color:#e4e4ef;overflow:hidden;display:flex;flex-direction:column;max-height:520px}
    .dv-header{display:flex;justify-content:space-between;align-items:center;padding:11px 14px;border-bottom:1px solid rgba(255,255,255,.07);font-weight:700;font-size:.88rem;background:#0a0e17;flex-shrink:0}
    .dv-close{background:none;border:none;color:#9494a8;cursor:pointer;font-size:1rem;padding:2px 6px;border-radius:4px;line-height:1}
    .dv-close:hover{background:rgba(255,255,255,.1);color:#e4e4ef}
    .dv-body{padding:12px;overflow-y:auto;flex:1}
    .dv-status{color:#9494a8;font-size:.82rem;margin-bottom:8px}
    .dv-fact{background:#1a2035;border:1px solid rgba(255,255,255,.07);border-radius:8px;padding:9px 11px;margin-bottom:7px;font-size:.8rem;cursor:pointer;transition:border-color .15s;display:flex;align-items:flex-start;gap:8px}
    .dv-fact:hover{border-color:rgba(124,92,252,.35)}
    .dv-fact.dv-selected{border-color:#7c5cfc;background:rgba(124,92,252,.1)}
    .dv-check{width:15px;height:15px;border:2px solid rgba(255,255,255,.2);border-radius:3px;flex-shrink:0;margin-top:1px;display:flex;align-items:center;justify-content:center;font-size:.65rem;color:#fff}
    .dv-fact.dv-selected .dv-check{background:#7c5cfc;border-color:#7c5cfc}
    .dv-fact-text{flex:1;line-height:1.5}
    .dv-subj{color:#a78bfa;font-weight:600}
    .dv-pred{color:#6a6a80}
    .dv-obj{color:#a78bfa;font-weight:600}
    .dv-actions{display:flex;gap:7px;margin-top:10px}
    .dv-btn{flex:1;background:#7c5cfc;color:#fff;border:none;border-radius:7px;padding:8px;font-weight:600;font-size:.8rem;cursor:pointer;font-family:inherit;transition:background .15s}
    .dv-btn:hover{background:#6a4de0}
    .dv-btn:disabled{opacity:.45;cursor:not-allowed}
    .dv-btn-ghost{background:rgba(255,255,255,.04);color:#9494a8;border:1px solid rgba(255,255,255,.09)}
    .dv-btn-ghost:hover{border-color:#a78bfa;color:#a78bfa;background:transparent}
    .dv-input{width:100%;background:#1a2035;border:1px solid rgba(255,255,255,.09);border-radius:7px;padding:7px 9px;color:#e4e4ef;font-size:.8rem;font-family:inherit;outline:none;margin-bottom:7px;transition:border-color .15s;box-sizing:border-box}
    .dv-input:focus{border-color:#7c5cfc}
    .dv-input::placeholder{color:#4a4a60}
    .dv-label{font-size:.72rem;color:#9494a8;font-weight:500;margin-bottom:3px;display:block}
    .dv-success{color:#34d399;font-size:.82rem;text-align:center;padding:8px}
    .dv-error{color:#ef4444;font-size:.78rem;padding:6px 0}
  `;
  document.head.appendChild(s);
}

function removePanel() { if (panel) { panel.remove(); panel = null; } }

function makePanel(titleText) {
  removePanel();
  injectStyles();
  panel = document.createElement('div');
  panel.className = 'dv-panel';
  panel.innerHTML = `
    <div class="dv-header">
      <span>🔮 ${titleText}</span>
      <button class="dv-close" id="dv-close-btn">✕</button>
    </div>
    <div class="dv-body" id="dv-body"></div>
  `;
  document.body.appendChild(panel);
  panel.querySelector('#dv-close-btn').onclick = removePanel;
  return panel.querySelector('#dv-body');
}

// ── Quick Save (right-click on selected text) ────────────────
function showQuickSave(selection) {
  const body = makePanel('DejaView — Save Fact');
  body.innerHTML = `
    <span class="dv-label">Subject</span>
    <input class="dv-input" id="dv-qs-subject" placeholder="Who or what" value="${esc(selection.split(' ').slice(0,3).join(' '))}">
    <span class="dv-label">Predicate</span>
    <input class="dv-input" id="dv-qs-predicate" placeholder="e.g. works_at, founded, knows" list="dv-pred-list">
    <datalist id="dv-pred-list">
      <option value="works_at"><option value="founded"><option value="knows">
      <option value="has_status"><option value="built_with"><option value="manages">
      <option value="attended"><option value="decided"><option value="expert_in">
    </datalist>
    <span class="dv-label">Object</span>
    <input class="dv-input" id="dv-qs-object" placeholder="The related entity or value">
    <div class="dv-actions">
      <button class="dv-btn" id="dv-qs-save">Save</button>
      <button class="dv-btn dv-btn-ghost" id="dv-qs-cancel">Cancel</button>
    </div>
    <div id="dv-qs-msg"></div>
  `;
  document.getElementById('dv-qs-cancel').onclick = removePanel;
  document.getElementById('dv-qs-save').onclick = () => {
    const subject   = document.getElementById('dv-qs-subject').value.trim();
    const predicate = document.getElementById('dv-qs-predicate').value.trim();
    const object    = document.getElementById('dv-qs-object').value.trim();
    const msg       = document.getElementById('dv-qs-msg');
    if (!subject || !predicate || !object) {
      msg.innerHTML = '<div class="dv-error">All three fields required.</div>';
      return;
    }
    const btn = document.getElementById('dv-qs-save');
    btn.disabled = true; btn.textContent = 'Saving...';
    chrome.runtime.sendMessage({
      type: 'API_CALL', method: 'POST', path: '/v1/facts',
      body: { facts: [{ subject, predicate, object, source: 'browser-extension', source_url: location.href }] },
    }, (r) => {
      if (r?.ok) {
        body.innerHTML = '<div class="dv-success">✅ Saved!<br><span style="color:#6a6a80;font-size:.75rem">' + esc(subject) + ' → ' + esc(predicate) + ' → ' + esc(object) + '</span></div>';
        setTimeout(removePanel, 1800);
      } else {
        btn.disabled = false; btn.textContent = 'Save';
        msg.innerHTML = '<div class="dv-error">' + esc(r?.error || 'Save failed') + '</div>';
      }
    });
  };
  // Enter key on last field saves
  document.getElementById('dv-qs-object').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('dv-qs-save').click();
  });
  document.getElementById('dv-qs-subject').focus();
}

// ── Extract (AI fact extraction from page) ───────────────────
function showExtractionPanel(text) {
  const body = makePanel('DejaView — Extract Facts');
  body.innerHTML = '<div class="dv-status" id="dv-ext-status">Extracting facts from this page...</div><div id="dv-ext-facts"></div><div class="dv-actions" id="dv-ext-actions" style="display:none"><button class="dv-btn" id="dv-ext-save">Save selected</button><button class="dv-btn dv-btn-ghost" id="dv-ext-dismiss">Dismiss</button></div>';

  document.getElementById('dv-ext-dismiss')?.addEventListener('click', removePanel);

  chrome.runtime.sendMessage({
    type: 'API_CALL', method: 'POST', path: '/v1/extract',
    body: { text, url: location.href, title: document.title },
  }, (resp) => {
    const statusEl  = document.getElementById('dv-ext-status');
    const factsEl   = document.getElementById('dv-ext-facts');
    const actionsEl = document.getElementById('dv-ext-actions');
    if (!resp?.ok) { statusEl.textContent = resp?.error || 'Extraction failed — is your API key set?'; return; }
    const facts = resp.data.facts || [];
    if (!facts.length) { statusEl.textContent = 'No facts found on this page.'; return; }
    statusEl.textContent = `${facts.length} fact${facts.length !== 1 ? 's' : ''} found — tap to deselect:`;
    facts.forEach((f, i) => {
      const div = document.createElement('div');
      div.className = 'dv-fact dv-selected';
      div.dataset.idx = i;
      div.innerHTML = `<div class="dv-check">✓</div><div class="dv-fact-text"><span class="dv-subj">${esc(f.subject)}</span> <span class="dv-pred">${esc(f.predicate)}</span> <span class="dv-obj">${esc(f.object)}</span></div>`;
      div.onclick = () => {
        div.classList.toggle('dv-selected');
        div.querySelector('.dv-check').textContent = div.classList.contains('dv-selected') ? '✓' : '';
      };
      factsEl.appendChild(div);
    });
    actionsEl.style.display = 'flex';
    document.getElementById('dv-ext-save').onclick = () => {
      const selected = [...document.querySelectorAll('.dv-fact.dv-selected')]
        .map(el => ({ ...facts[+el.dataset.idx], source: 'browser-extension', source_url: location.href }));
      if (!selected.length) return;
      const btn = document.getElementById('dv-ext-save');
      btn.disabled = true; btn.textContent = 'Saving...';
      chrome.runtime.sendMessage({
        type: 'API_CALL', method: 'POST', path: '/v1/facts',
        body: { facts: selected },
      }, (r) => {
        if (r?.ok) {
          statusEl.innerHTML = `<span style="color:#34d399">✅ Saved ${r.data.stored} fact${r.data.stored !== 1 ? 's' : ''}!</span>`;
          actionsEl.style.display = 'none';
          factsEl.querySelectorAll('.dv-fact').forEach(el => { el.style.opacity='.35'; el.style.pointerEvents='none'; });
          setTimeout(removePanel, 2200);
        } else {
          btn.disabled = false; btn.textContent = 'Save selected';
          statusEl.innerHTML = '<span style="color:#ef4444">Save failed: ' + esc(r?.error || 'unknown') + '</span>';
        }
      });
    };
  });
}

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
