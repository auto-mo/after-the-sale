// Product picker combobox in the header. ARIA combobox/listbox pattern with
// full keyboard support (arrows, Enter, Escape, type-to-search).

import { loadProducts, loadPortfolio } from './data.js?v=202609232353';
import { intFmt, humanizeType } from './format.js?v=202609232353';
import { view, setView, onViewChanged } from './state.js?v=202609232353';
import { navigate } from './router.js?v=202609232353';

const MAX_RESULTS = 60;

let products = [];
let familyTypeLabel = new Map(); // family code -> type label (from portfolio.families)

let root, btn, btnLabel, panel, searchInput, unitsCheck, accCheck, listEl, filterLabel;
let activeOptionEl = null;
let lastFocused = null;

function shortTitle(p) {
  // Strip a leading brand + model repeat so the row reads "AF101  Air Fryer that Crisps..."
  let t = p.title;
  if (p.model && t.startsWith(p.model)) t = t.slice(p.model.length).trim();
  return t;
}

function groupKeyOf(p) {
  return p.family || `__type:${p.type}`;
}

function groupLabelOf(key, p) {
  if (!key.startsWith('__type:')) {
    const typeLabel = humanizeType(familyTypeLabel.get(key) || p.type);
    return `${key} · ${typeLabel}`;
  }
  return humanizeType(p.type);
}

function buildGroups(list) {
  const groups = new Map();
  for (const p of list) {
    const key = groupKeyOf(p);
    if (!groups.has(key)) groups.set(key, { key, label: groupLabelOf(key, p), items: [], total: 0 });
    const g = groups.get(key);
    g.items.push(p);
    g.total += (p.reviews_new || 0) + (p.reviews_renewed || 0);
  }
  const arr = [...groups.values()];
  arr.forEach((g) => g.items.sort((a, b) => ((b.reviews_new || 0) + (b.reviews_renewed || 0)) - ((a.reviews_new || 0) + (a.reviews_renewed || 0))));
  arr.sort((a, b) => b.total - a.total);
  return arr;
}

function matches(p, q) {
  if (!q) return true;
  const hay = `${p.model || ''} ${p.title} ${p.brand}`.toLowerCase();
  return hay.includes(q.toLowerCase());
}

function friendlyLabel(p) {
  // "Ninja AF101 air fryer" style, matching the storyboard.
  const bits = [p.brand];
  if (p.model) bits.push(p.model);
  bits.push(humanizeType(p.type));
  return bits.join(' ');
}

function renderList() {
  const q = searchInput.value.trim();
  const wantUnits = unitsCheck.checked;
  const wantAcc = accCheck.checked;
  const filtered = products.filter((p) => {
    if (p.accessory && !wantAcc) return false;
    if (!p.accessory && !wantUnits) return false;
    return matches(p, q);
  });
  const total = filtered.length;
  const groups = buildGroups(filtered);

  listEl.innerHTML = '';
  const head = document.createElement('div');
  head.className = 'picker-list-head';
  head.innerHTML = '<span>Grouped by family</span><span>Reviews</span>';
  listEl.appendChild(head);

  if (total === 0) {
    const empty = document.createElement('div');
    empty.className = 'picker-empty';
    empty.textContent = 'No products match your search.';
    listEl.appendChild(empty);
    activeOptionEl = null;
    return;
  }

  let shown = 0;
  outer:
  for (const g of groups) {
    const gl = document.createElement('div');
    gl.className = 'picker-group-label';
    gl.setAttribute('role', 'presentation');
    gl.textContent = g.label;
    listEl.appendChild(gl);
    for (const p of g.items) {
      if (shown >= MAX_RESULTS) break outer;
      const opt = document.createElement('div');
      opt.className = 'picker-option';
      opt.setAttribute('role', 'option');
      opt.dataset.id = p.id;
      opt.setAttribute('aria-selected', p.id === view.productId ? 'true' : 'false');
      if (p.id === view.productId) activeOptionEl = opt;
      const title = document.createElement('span');
      title.className = 'picker-option-title';
      title.innerHTML = `<strong>${p.model || p.id}</strong> ${shortTitle(p)}`;
      const count = document.createElement('span');
      count.className = 'picker-option-count mono';
      count.textContent = intFmt((p.reviews_new || 0) + (p.reviews_renewed || 0));
      opt.appendChild(title);
      opt.appendChild(count);
      opt.addEventListener('click', () => selectProduct(p.id));
      listEl.appendChild(opt);
      shown += 1;
    }
  }
  if (total > shown) {
    const note = document.createElement('div');
    note.className = 'picker-refine';
    note.textContent = `Showing ${shown} of ${total}. Refine your search to see more.`;
    listEl.appendChild(note);
  }
}

function selectProduct(id) {
  closePanel();
  setView({ productId: id, from: null, to: null });
  navigate(`/product/${id}`);
  btn.focus();
}

function openPanel() {
  panel.hidden = false;
  btn.setAttribute('aria-expanded', 'true');
  lastFocused = document.activeElement;
  renderList();
  searchInput.value = '';
  searchInput.focus();
  document.addEventListener('keydown', onDocKeydown, true);
  document.addEventListener('click', onDocClick, true);
}

function closePanel() {
  if (panel.hidden) return;
  panel.hidden = true;
  btn.setAttribute('aria-expanded', 'false');
  document.removeEventListener('keydown', onDocKeydown, true);
  document.removeEventListener('click', onDocClick, true);
}

function onDocClick(e) {
  if (!root.contains(e.target)) closePanel();
}

function moveActive(delta) {
  const opts = [...listEl.querySelectorAll('[role="option"]')];
  if (!opts.length) return;
  let idx = activeOptionEl ? opts.indexOf(activeOptionEl) : -1;
  idx = (idx + delta + opts.length) % opts.length;
  if (activeOptionEl) activeOptionEl.classList.remove('picker-option-active');
  activeOptionEl = opts[idx];
  activeOptionEl.scrollIntoView({ block: 'nearest' });
  activeOptionEl.classList.add('picker-option-active');
}

function onDocKeydown(e) {
  if (e.key === 'Escape') {
    e.preventDefault();
    closePanel();
    btn.focus();
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    moveActive(1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    moveActive(-1);
  } else if (e.key === 'Enter') {
    if (activeOptionEl) {
      e.preventDefault();
      selectProduct(activeOptionEl.dataset.id);
    }
  }
}

export async function initPicker(container) {
  root = document.createElement('div');
  root.className = 'picker-wrap';
  root.innerHTML = `
    <span id="picker-plab" class="picker-label">Product</span>
    <button type="button" id="picker-btn" class="picker-btn" aria-haspopup="listbox" aria-expanded="false" aria-labelledby="picker-plab picker-btn">
      <span class="picker-btn-label">Loading products…</span>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
    </button>
    <div id="picker-panel" class="picker-panel" role="dialog" aria-label="Choose a product" hidden>
      <div class="picker-search-area">
        <label class="picker-search-label" for="picker-search" id="picker-search-label">Search products</label>
        <input id="picker-search" type="search" placeholder="Model or name, such as AF101 or Navigator" autocomplete="off">
        <div class="picker-filters">
          <label><input id="picker-filter-units" type="checkbox" checked>Units</label>
          <label><input id="picker-filter-acc" type="checkbox">Accessories</label>
        </div>
      </div>
      <div id="picker-list" role="listbox" aria-label="Products" class="picker-list"></div>
    </div>
  `;
  container.appendChild(root);

  btn = root.querySelector('#picker-btn');
  btnLabel = btn.querySelector('.picker-btn-label');
  panel = root.querySelector('#picker-panel');
  searchInput = root.querySelector('#picker-search');
  unitsCheck = root.querySelector('#picker-filter-units');
  accCheck = root.querySelector('#picker-filter-acc');
  listEl = root.querySelector('#picker-list');
  filterLabel = root.querySelector('#picker-search-label');

  btn.addEventListener('click', () => {
    if (panel.hidden) openPanel(); else closePanel();
  });
  searchInput.addEventListener('input', renderList);
  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      // handled by document listener too, but stop native caret movement
    }
  });
  unitsCheck.addEventListener('change', renderList);
  accCheck.addEventListener('change', renderList);

  try {
    const [productList, portfolio] = await Promise.all([loadProducts(), loadPortfolio()]);
    products = productList;
    familyTypeLabel = new Map(portfolio.families.map((f) => [f.family, f.type]));
    const unitsCount = products.filter((p) => !p.accessory).length;
    const accCount = products.filter((p) => p.accessory).length;
    filterLabel.textContent = `Search ${intFmt(unitsCount)} products and ${intFmt(accCount)} accessories and bundles`;
    updateButtonLabel();
  } catch (err) {
    btnLabel.textContent = 'Products unavailable';
    btn.disabled = true;
  }

  onViewChanged(updateButtonLabel);
}

function updateButtonLabel() {
  if (!products.length) return;
  const p = products.find((x) => x.id === view.productId);
  btnLabel.textContent = p ? friendlyLabel(p) : 'Choose a product';
}

/** Called by the router when the URL names a product not yet reflected in
 * the picker's idea of "current product" (e.g. deep link or back button). */
export function syncPickerToProduct(id) {
  if (view.productId !== id) setView({ productId: id });
  else updateButtonLabel();
}
