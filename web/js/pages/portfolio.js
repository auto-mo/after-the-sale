import { loadPortfolio, loadProducts } from '../data.js?v=202609241634';
import { intFmt, decFmt, humanizeType } from '../format.js?v=202609241634';
import { setView } from '../state.js?v=202609241634';
import { navigate } from '../router.js?v=202609241634';

function themeLabelMap(portfolio) {
  return new Map(portfolio.themes.map((t) => [t.key, t.label]));
}

function sortIconSvg(state) {
  if (state === 'ascending') return '<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M5 2l3 4H2z" fill="currentColor"/></svg>';
  if (state === 'descending') return '<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M5 8L2 4h6z" fill="currentColor"/></svg>';
  return '<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" style="opacity:.35"><path d="M5 1l2.5 3h-5zM5 9l-2.5-3h5z" fill="currentColor"/></svg>';
}

function findingsLink(anchor) {
  return `#/findings?anchor=${anchor}`;
}

/** Build the five key-findings statements from portfolio.findings, per spec:
 * drift, trend, types.biggest_gap, fail, refurb. Each links to its Findings section. */
function buildKeyFindings(portfolio) {
  const labels = themeLabelMap(portfolio);
  const out = [];

  const { drift } = portfolio.findings;
  out.push({
    anchor: 'drift',
    html: `<strong>${drift.sharkninja.fell} of ${drift.sharkninja.products}</strong> SharkNinja products rated lower in years 3 to 4 than in year 1, in line with peer brands (${drift.peers.fell} of ${drift.peers.products}).`,
  });

  // 2015 to 2022: the first year with steady volume in every compared type, and the last full year.
  const at = (set, yr) => portfolio.findings.trend.find((r) => r.brand_set === set && r.yr === yr);
  const sn15 = at('SharkNinja', 2015); const sn22 = at('SharkNinja', 2022);
  const pe15 = at('Peers', 2015); const pe22 = at('Peers', 2022);
  if (sn15 && sn22 && pe15 && pe22) {
    out.push({
      anchor: 'trend',
      html: `The share of 1 and 2-star reviews rose for everyone from 2015 to 2022: SharkNinja <strong>${decFmt(sn15.low_share * 100, 0)}% to ${decFmt(sn22.low_share * 100, 0)}%</strong>, peer brands ${decFmt(pe15.low_share * 100, 0)}% to ${decFmt(pe22.low_share * 100, 0)}%.`,
    });
  }

  let biggest = null;
  for (const t of portfolio.types) {
    const g = t.biggest_gap && t.biggest_gap[0];
    if (!g) continue;
    const diff = (g.sn || 0) - (g.peers || 0);
    if (!biggest || diff > biggest.diff) biggest = { type: t.type, theme: g.theme, sn: g.sn, peers: g.peers, diff };
  }
  if (biggest) {
    const ratio = biggest.peers > 0 ? biggest.sn / biggest.peers : null;
    const ratioText = ratio && ratio >= 1.3 ? `, about ${decFmt(ratio, 1)}x the peer rate` : '';
    out.push({
      anchor: 'complaints',
      html: `For ${humanizeType(biggest.type)}s, SharkNinja&rsquo;s signature complaint is <strong>${(labels.get(biggest.theme) || biggest.theme).toLowerCase()}</strong>: ${decFmt(biggest.sn * 100, 1)}% of low-star reviews versus ${decFmt(biggest.peers * 100, 1)}% for peers${ratioText}.`,
    });
  }

  const fs = portfolio.findings.fail.summary.filter((x) => x.product_type === 'All types');
  const fsn = fs.find((x) => x.brand_set === 'SharkNinja');
  const fpe = fs.find((x) => x.brand_set === 'Peers');
  if (fsn && fpe) {
    out.push({
      anchor: 'failure',
      html: `Owners who say when a product stopped working typically say about <strong>${decFmt(fsn.median_months, 0)} months</strong> for SharkNinja and ${decFmt(fpe.median_months, 0)} for peer brands (median of ${intFmt(fsn.n)} and ${intFmt(fpe.n)} reviews that state a time).`,
    });
  }

  const r = portfolio.findings.refurb;
  out.push({
    anchor: 'refurb',
    html: `Refurbished units rate about the same as new ones for the same product in the same year (<strong>${decFmt(r.mean_gap, 2)} stars</strong> on average); what differs is arrival, with missing parts in ${decFmt(r.arrival.missing_parts.refurbished * 100, 1)}% of their low-star reviews versus ${decFmt(r.arrival.missing_parts.new * 100, 1)}% for new.`,
  });

  return out.slice(0, 5);
}

const FAMILY_COLUMNS = [
  { key: 'family', label: 'Family', type: 'text', heading: 'Product families by family code', accessor: (f) => f.family },
  { key: 'type', label: 'Main type', type: 'text', heading: 'Product families by main type', accessor: (f) => humanizeType(f.type) },
  { key: 'products', label: 'Products', type: 'num', heading: 'Largest product families by products', accessor: (f) => f.products },
  { key: 'reviews_total', label: 'Review volume', type: 'num', heading: 'Largest product families by review volume', accessor: (f) => f.reviews_new + f.reviews_renewed },
  { key: 'low_share', label: '1 and 2-star share', type: 'num', heading: 'Largest product families by 1 and 2-star share', accessor: (f) => (f.low_share === null || f.low_share === undefined ? -1 : f.low_share) },
  { key: 'top_theme', label: 'Most common complaint', type: 'text', heading: 'Product families by most common complaint', accessor: (f, labels) => (f.top_theme ? labels.get(f.top_theme) || f.top_theme : '') },
];

export async function render(container) {
  container.innerHTML = '<div class="empty-state">Loading overview…</div>';
  let portfolio, products;
  try {
    [portfolio, products] = await Promise.all([loadPortfolio(), loadProducts()]);
  } catch (err) {
    container.innerHTML = `<div class="error-state">Could not load the data for this page. ${err.message}</div>`;
    return;
  }

  const labels = themeLabelMap(portfolio);
  container.innerHTML = '';

  // ---- heading ----
  const heading = document.createElement('div');
  heading.className = 'overview-heading';
  heading.innerHTML = `
    <h1>After the Sale</h1>
    <p class="overview-subtitle">What Shark and Ninja owners report after they buy, compared with ${portfolio.stats.peer_brands.slice(0, -1).join(', ')} and ${portfolio.stats.peer_brands[portfolio.stats.peer_brands.length - 1]}.</p>
    <p class="overview-headline">Owners of both SharkNinja and peer brands grow less happy as products age; where SharkNinja differs is what they complain about.</p>
  `;
  container.appendChild(heading);

  // ---- key findings ----
  const list = document.createElement('ol');
  list.className = 'key-findings';
  for (const kf of buildKeyFindings(portfolio)) {
    const li = document.createElement('li');
    const num = document.createElement('span');
    num.className = 'kf-num';
    num.setAttribute('aria-hidden', 'true');
    num.textContent = String(list.children.length + 1);
    const text = document.createElement('span');
    text.className = 'kf-text';
    text.innerHTML = `${kf.html} <a href="${findingsLink(kf.anchor)}">See the finding</a>`;
    li.appendChild(num);
    li.appendChild(text);
    list.appendChild(li);
  }
  container.appendChild(list);

  // ---- product types table ----
  const typesHead = document.createElement('div');
  typesHead.className = 'families-head';
  typesHead.innerHTML = '<h2>Product types</h2>';
  container.appendChild(typesHead);

  const typesWrap = document.createElement('div');
  typesWrap.className = 'families-table-wrap';
  const typesTable = document.createElement('table');
  typesTable.className = 'types-table';
  typesTable.innerHTML = `
    <thead><tr>
      <th scope="col">Type</th>
      <th scope="col" class="num">1 and 2-star share</th>
      <th scope="col">Biggest complaint gap</th>
      <th scope="col" class="num">Rating change in stars, year 1 to years 3 to 4</th>
      <th scope="col" class="num">Typical stated time to failure</th>
    </tr></thead>
    <tbody></tbody>
  `;
  const typesBody = typesTable.querySelector('tbody');
  for (const t of [...portfolio.types].sort((a, b) => (t2n(b) - t2n(a)))) {
    const tr = document.createElement('tr');
    const sn = t.low_share.SharkNinja;
    const pe = t.low_share.Peers;
    const gap = t.biggest_gap && t.biggest_gap[0];
    const driftText = fewOrValue(t.drift_sn_n, t.drift_sn) + ' vs ' + fewOrValue(t.drift_peers_n, t.drift_peers);
    const failText = `${t.fail_median_sn ?? '–'} mo vs ${t.fail_median_peers ?? '–'} mo`;
    tr.innerHTML = `
      <td><span class="type-name">${humanizeType(t.type)}</span><span class="type-cap">vs ${t.peer_brands.join(', ') || 'peers'}</span></td>
      <td class="mono num">${decFmt(sn * 100, 1)}% <span class="few-note">vs ${decFmt(pe * 100, 1)}%</span></td>
      <td>${gap ? `<div class="gap-cell"><span class="gap-theme">${labels.get(gap.theme) || gap.theme}</span><span class="gap-nums mono">${decFmt(gap.sn * 100, 1)}% vs ${decFmt(gap.peers * 100, 1)}%</span></div>` : '–'}</td>
      <td class="mono num">${driftText}</td>
      <td class="mono num">${failText}</td>
    `;
    typesBody.appendChild(tr);
  }
  typesWrap.appendChild(typesTable);
  container.appendChild(typesWrap);

  function t2n(t) { return (t.n_low_sn || 0) + (t.n_low_peers || 0); }
  function fewOrValue(n, v) {
    if (!n || n < 5) return 'few products';
    return `${v > 0 ? '+' : ''}${decFmt(v, 2)}`;
  }

  // ---- product families table ----
  const head = document.createElement('div');
  head.className = 'families-head';
  const h2 = document.createElement('h2');
  head.appendChild(h2);
  const filterRow = document.createElement('div');
  filterRow.className = 'filter-row';
  const typeLabel = document.createElement('label');
  typeLabel.setAttribute('for', 'ptype');
  typeLabel.textContent = 'Product type';
  const typeSelect = document.createElement('select');
  typeSelect.id = 'ptype';
  const types = [...new Set(portfolio.families.map((f) => f.type))].sort();
  typeSelect.innerHTML = ['<option value="">All types</option>', ...types.map((t) => `<option value="${t}">${humanizeType(t)}</option>`)].join('');
  filterRow.appendChild(typeLabel);
  filterRow.appendChild(typeSelect);
  head.appendChild(filterRow);
  container.appendChild(head);

  const tableWrap = document.createElement('div');
  tableWrap.className = 'families-table-wrap';
  const table = document.createElement('table');
  table.className = 'families-table';
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  table.appendChild(tbody);

  const sortState = { key: 'reviews_total', dir: 'desc' };

  function familyLargestProduct(familyCode) {
    const inFamily = products.filter((p) => p.family === familyCode);
    if (!inFamily.length) return null;
    return inFamily.reduce((a, b) => (((b.reviews_new || 0) + (b.reviews_renewed || 0)) > ((a.reviews_new || 0) + (a.reviews_renewed || 0)) ? b : a));
  }

  function openFamily(familyCode) {
    const p = familyLargestProduct(familyCode);
    if (!p) return;
    setView({ productId: p.id, from: null, to: null });
    navigate(`/product/${p.id}`);
  }

  function drawHeader() {
    headRow.innerHTML = '';
    for (const col of FAMILY_COLUMNS) {
      const th = document.createElement('th');
      th.scope = 'col';
      if (col.type === 'num') th.classList.add('num');
      const active = sortState.key === col.key;
      const ariaState = active ? (sortState.dir === 'asc' ? 'ascending' : 'descending') : 'none';
      th.setAttribute('aria-sort', ariaState);
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'sort-btn';
      btn.innerHTML = `<span>${col.label}</span>${sortIconSvg(active ? ariaState : 'none')}`;
      btn.addEventListener('click', () => {
        if (sortState.key === col.key) {
          sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
        } else {
          sortState.key = col.key;
          sortState.dir = col.type === 'num' ? 'desc' : 'asc';
        }
        drawHeader();
        drawTable();
      });
      th.appendChild(btn);
      headRow.appendChild(th);
    }
  }

  function drawTable() {
    const col = FAMILY_COLUMNS.find((c) => c.key === sortState.key);
    h2.textContent = col.heading;
    const filterType = typeSelect.value;
    const rows = [...portfolio.families].filter((f) => !filterType || f.type === filterType);
    rows.sort((a, b) => {
      const av = col.accessor(a, labels);
      const bv = col.accessor(b, labels);
      let cmp;
      if (col.type === 'num') cmp = av - bv;
      else cmp = String(av).localeCompare(String(bv));
      return sortState.dir === 'asc' ? cmp : -cmp;
    });
    tbody.innerHTML = '';
    for (const f of rows) {
      const total = f.reviews_new + f.reviews_renewed;
      const tr = document.createElement('tr');
      tr.tabIndex = 0;
      tr.setAttribute('role', 'button');
      tr.setAttribute('aria-label', `Open ${f.family}, ${humanizeType(f.type)}`);
      const lowShare = f.low_share === null || f.low_share === undefined ? '–' : `${decFmt(f.low_share * 100, 1)}%`;
      const topTheme = f.top_theme ? (labels.get(f.top_theme) || f.top_theme) : '';
      tr.innerHTML = `
        <td class="mono">${f.family}</td><td>${humanizeType(f.type)}</td>
        <td class="mono num">${intFmt(f.products)}</td>
        <td class="mono num">${intFmt(total)}</td>
        <td class="mono num">${lowShare}</td>
        <td>${topTheme}</td>
      `;
      tr.addEventListener('click', () => openFamily(f.family));
      tr.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openFamily(f.family); }
      });
      tbody.appendChild(tr);
    }
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No families match this filter.</td></tr>';
    }
  }
  typeSelect.addEventListener('change', drawTable);
  drawHeader();
  drawTable();

  tableWrap.appendChild(table);
  container.appendChild(tableWrap);
}
