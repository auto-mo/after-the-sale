import { findProduct } from './data.js?v=202609232353';
import { getView, setView, getPreviousView } from './state.js?v=202609232353';
import { navigate } from './router.js?v=202609232353';
import { monthShort } from './format.js?v=202609232353';

const MAX_LEN = 1000;
let messages = [];
let drawerOpen = false;
let offline = false;
let lastFocused = null;

let root, overlay, drawer, body, input, counter, sendBtn, suggestionsEl, offlineNote;

function currentRouteInfo() {
  const hash = (window.location.hash || '#/').slice(1);
  const parts = hash.split('/').filter(Boolean);
  if (parts[0] === 'product' && parts[1]) return { onProduct: true, productId: parts[1] };
  return { onProduct: false, productId: null };
}

// Model replies may use light markdown (**bold**, "- " or "1. " lists, "#" headings). Render it with DOM text
// nodes only (never innerHTML), so nothing in a reply can inject markup.
function appendInline(el, text) {
  const parts = String(text).replace(/^#+\s*/, '').split(/\*\*(.+?)\*\*/g);
  parts.forEach((part, i) => {
    if (!part) return;
    if (i % 2 === 1) {
      const b = document.createElement('strong');
      b.textContent = part;
      el.appendChild(b);
    } else {
      el.appendChild(document.createTextNode(part));
    }
  });
}

function renderMessageContent(container, text) {
  const paragraphs = String(text).split(/\n{2,}/);
  for (const para of paragraphs) {
    const lines = para.split('\n').filter((l) => l.trim() !== '');
    const bullet = lines.length > 0 && lines.every((l) => /^[-*]\s+/.test(l.trim()));
    const numbered = lines.length > 0 && lines.every((l) => /^\d+[.)]\s+/.test(l.trim()));
    if (bullet || numbered) {
      const list = document.createElement(numbered ? 'ol' : 'ul');
      list.style.margin = '4px 0';
      list.style.paddingLeft = '20px';
      for (const l of lines) {
        const li = document.createElement('li');
        appendInline(li, l.trim().replace(/^([-*]|\d+[.)])\s+/, ''));
        list.appendChild(li);
      }
      container.appendChild(list);
    } else {
      const p = document.createElement('p');
      p.style.margin = '0 0 6px';
      lines.forEach((l, i) => {
        if (i) p.appendChild(document.createElement('br'));
        appendInline(p, l);
      });
      container.appendChild(p);
    }
  }
}

function addMessage({ role, content, tools, viewChip, isSystem }) {
  const msg = document.createElement('div');
  msg.className = `chat-msg ${isSystem ? 'system' : role}`;
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';
  renderMessageContent(bubble, content);
  msg.appendChild(bubble);

  if (tools && tools.length) {
    const details = document.createElement('details');
    details.className = 'chat-tools';
    const summary = document.createElement('summary');
    summary.textContent = 'Based on: ' + tools.map((t) => t.name).join(', ');
    details.appendChild(summary);
    const list = document.createElement('div');
    list.style.marginTop = '4px';
    for (const t of tools) {
      const line = document.createElement('div');
      line.textContent = `${t.name}: ${t.summary}`;
      list.appendChild(line);
    }
    details.appendChild(list);
    msg.appendChild(details);
  }

  if (viewChip) {
    const chip = document.createElement('div');
    chip.className = 'chat-view-chip';
    const label = document.createElement('span');
    label.textContent = viewChip.label;
    const undo = document.createElement('button');
    undo.type = 'button';
    undo.textContent = 'Undo';
    undo.addEventListener('click', () => {
      if (viewChip.previous) {
        setView(viewChip.previous);
        navigate(`/product/${viewChip.previous.productId}`);
      }
      chip.remove();
    });
    chip.appendChild(label);
    chip.appendChild(undo);
    msg.appendChild(chip);
  }

  body.appendChild(msg);
  body.scrollTop = body.scrollHeight;
}

function viewChipLabel(v, product) {
  const name = (product && (product.model || product.id)) || v.productId;
  const range = v.from && v.to ? `${monthShort(v.from)}–${monthShort(v.to)}` : 'full range';
  const chans = [];
  if (v.channels.new) chans.push('new');
  if (v.channels.renewed) chans.push('refurbished');
  return `Set: ${name} · ${range} · ${chans.join(' + ') || 'no channels'} units · ${v.measure}`;
}

async function applyServerView(serverView) {
  const previous = getPreviousView() || getView();
  setView({
    productId: serverView.product_id,
    from: serverView.from ?? null,
    to: serverView.to ?? null,
    channels: {
      new: !serverView.channels || serverView.channels.includes('new'),
      renewed: !serverView.channels || serverView.channels.includes('renewed'),
    },
    measure: serverView.measure || 'volume',
  }, { remember: true });
  navigate(`/product/${serverView.product_id}`);
  let product = null;
  try { product = await findProduct(serverView.product_id); } catch { /* ignore */ }
  return { label: viewChipLabel(getView(), product), previous };
}

async function sendMessage(text) {
  const trimmed = text.trim().slice(0, MAX_LEN);
  if (!trimmed) return;
  messages.push({ role: 'user', content: trimmed });
  addMessage({ role: 'user', content: trimmed });
  input.value = '';
  updateCounter();

  const thinking = document.createElement('div');
  thinking.className = 'chat-msg assistant';
  thinking.innerHTML = '<div class="chat-bubble">Thinking…</div>';
  body.appendChild(thinking);
  body.scrollTop = body.scrollHeight;

  let payload;
  try {
    const res = await fetch('api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, view: getView(), turnstile_token: null }),
    });
    if (!res.ok) throw new Error(`status ${res.status}`);
    payload = await res.json();
  } catch (err) {
    thinking.remove();
    offline = true;
    showOfflineNote();
    return;
  }
  thinking.remove();
  offline = false;
  if (offlineNote) offlineNote.hidden = true;

  if (payload.limited) {
    addMessage({ role: 'assistant', content: 'You have reached the message limit for now. Try again in a while.', isSystem: true });
    return;
  }

  messages.push({ role: 'assistant', content: payload.reply || '' });
  let viewChip = null;
  if (payload.view) {
    try {
      viewChip = await applyServerView(payload.view);
    } catch { /* ignore malformed view */ }
  }
  addMessage({ role: 'assistant', content: payload.reply || '(no reply)', tools: payload.tools, viewChip });

  if (payload.paused && payload.message) {
    addMessage({ role: 'assistant', content: payload.message, isSystem: true });
  }
}

function showOfflineNote() {
  if (!offlineNote) return;
  offlineNote.hidden = false;
  offlineNote.textContent = 'The assistant is offline right now; the rest of the tool still works.';
}

function updateCounter() {
  counter.textContent = `${input.value.length} / ${MAX_LEN}`;
}

function buildSuggestions() {
  suggestionsEl.innerHTML = '';
  const { onProduct, productId } = currentRouteInfo();
  const chips = [];
  if (onProduct) {
    findProduct(productId).then((product) => {
      const name = (product && (product.model || product.id)) || productId;
      const productChips = [
        `Show ${name} from Jan 2019 to Dec 2020, new units only`,
        `What did buyers complain about in ${name}'s low-rating months?`,
        `How do refurbished reviews of ${name} differ from new ones?`,
        `Why is this verdict "No clear change"?`,
      ];
      renderChips([...productChips, ...everywhereChips()]);
    }).catch(() => renderChips(everywhereChips()));
  } else {
    renderChips(everywhereChips());
  }
}

function everywhereChips() {
  return [
    'Which air fryers have the most refurbished reviews?',
    'Which product families grew most in 2021?',
    'Find cases of cannibalisation',
    'Which products dropped most after refurbished units appeared?',
    "What can't this tool tell me?",
  ];
}

function renderChips(list) {
  suggestionsEl.innerHTML = '';
  for (const text of list) {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chat-chip';
    chip.textContent = text;
    chip.addEventListener('click', () => sendMessage(text));
    suggestionsEl.appendChild(chip);
  }
}

function openDrawer() {
  drawerOpen = true;
  lastFocused = document.activeElement;
  overlay.hidden = false;
  document.addEventListener('keydown', onKeydown);
  buildSuggestions();
  input.focus();
}

function closeDrawer() {
  drawerOpen = false;
  overlay.hidden = true;
  document.removeEventListener('keydown', onKeydown);
  if (lastFocused && lastFocused.focus) lastFocused.focus();
}

function onKeydown(e) {
  if (e.key === 'Escape') closeDrawer();
}

export function initChat(rootEl, askBtn) {
  root = rootEl;
  root.innerHTML = `
    <div class="chat-overlay" id="chat-overlay" hidden>
      <div class="chat-drawer" role="dialog" aria-modal="true" aria-labelledby="chat-title">
        <div class="chat-header">
          <h2 id="chat-title">Ask about the data</h2>
          <button type="button" class="chat-close" aria-label="Close chat">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="chat-body" id="chat-body"></div>
        <p class="chat-offline-note" id="chat-offline-note" hidden></p>
        <div class="chat-suggestions" id="chat-suggestions"></div>
        <div class="chat-input-row">
          <div class="chat-input-area">
            <textarea id="chat-input" rows="2" maxlength="1000" placeholder="Ask a question about this data…" aria-label="Message"></textarea>
            <button type="button" id="chat-send" class="btn btn-primary">Send</button>
          </div>
          <span class="chat-counter" id="chat-counter">0 / 1000</span>
        </div>
      </div>
    </div>
  `;
  overlay = root.querySelector('#chat-overlay');
  drawer = root.querySelector('.chat-drawer');
  body = root.querySelector('#chat-body');
  input = root.querySelector('#chat-input');
  counter = root.querySelector('#chat-counter');
  sendBtn = root.querySelector('#chat-send');
  suggestionsEl = root.querySelector('#chat-suggestions');
  offlineNote = root.querySelector('#chat-offline-note');

  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeDrawer(); });
  root.querySelector('.chat-close').addEventListener('click', closeDrawer);
  askBtn.addEventListener('click', () => (drawerOpen ? closeDrawer() : openDrawer()));
  input.addEventListener('input', updateCounter);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input.value);
    }
  });
  sendBtn.addEventListener('click', () => sendMessage(input.value));

  if (!messages.length) {
    addMessage({
      role: 'assistant',
      isSystem: true,
      content: "Ask about any product's numbers, or ask me to set the view for you, for example a date range or which channels to show.",
    });
  }
}

export function openChatDrawer() {
  openDrawer();
}
