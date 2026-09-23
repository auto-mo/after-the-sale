import { loadPortfolio, loadProducts } from '../data.js?v=202609232353';
import { renderVolumeChart } from '../charts.js?v=202609232353';
import { intFmt, monthLong, humanizeType } from '../format.js?v=202609232353';
import { setView } from '../state.js?v=202609232353';
import { navigate } from '../router.js?v=202609232353';

function computeTakeaway(months, completeThrough) {
  const byYear = new Map();
  for (const row of months) {
    const y = Number(row.m.slice(0, 4));
    const total = (row.new || 0) + (row.renewed || 0);
    byYear.set(y, (byYear.get(y) || 0) + total);
  }
  const years = [...byYear.keys()].sort((a, b) => a - b);
  if (!years.length) return 'Review volume over time';
  const peak = Math.max(...byYear.values());
  const startYear = years.find((y) => byYear.get(y) >= peak * 0.05) ?? years[0];
  const lastFullYear = Number(completeThrough.slice(0, 4)) - 1;
  const endYear = byYear.has(lastFullYear) ? lastFullYear : years[years.length - 1];
  const startTotal = byYear.get(startYear) || 1;
  const endTotal = byYear.get(endYear) || 0;
  const ratio = endTotal / startTotal;
  const ratioText = ratio >= 10 ? `${Math.round(ratio)}×` : `${ratio.toFixed(1)}×`;
  const monthName = monthLong(completeThrough);
  return `Review volume grew about ${ratioText} from ${startYear} to ${endYear}; data thins after ${monthName}`;
}

const COLUMNS = [
  { key: 'family', label: 'Family', type: 'text', heading: 'Product families by family code', accessor: (f) => f.family },
  { key: 'type', label: 'Main type', type: 'text', heading: 'Product families by main type', accessor: (f) => humanizeType(f.type) },
  { key: 'products', label: 'Products', type: 'num', heading: 'Largest product families by products', accessor: (f) => f.products },
  { key: 'reviews_new', label: 'New-unit reviews', type: 'num', heading: 'Largest product families by new-unit reviews', accessor: (f) => f.reviews_new },
  { key: 'reviews_renewed', label: 'Refurbished reviews', type: 'num', heading: 'Largest product families by refurbished reviews', accessor: (f) => f.reviews_renewed },
  {
    key: 'share',
    label: 'Refurbished share',
    type: 'num',
    heading: 'Largest product families by refurbished share',
    accessor: (f) => { const t = f.reviews_new + f.reviews_renewed; return t > 0 ? f.reviews_renewed / t : 0; },
  },
];

function sortIconSvg(state) {
  if (state === 'ascending') return '<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M5 2l3 4H2z" fill="currentColor"/></svg>';
  if (state === 'descending') return '<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M5 8L2 4h6z" fill="currentColor"/></svg>';
  return '<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" style="opacity:.35"><path d="M5 1l2.5 3h-5zM5 9l-2.5-3h5z" fill="currentColor"/></svg>';
}

export async function render(container) {
  container.innerHTML = '<div class="empty-state">Loading portfolio…</div>';
  let portfolio, products;
  try {
    [portfolio, products] = await Promise.all([loadPortfolio(), loadProducts()]);
  } catch (err) {
    container.innerHTML = `<div class="error-state">Could not load portfolio data. ${err.message}</div>`;
    return;
  }

  container.innerHTML = '';

  const title = document.createElement('h1');
  title.className = 'portfolio-title';
  title.textContent = computeTakeaway(portfolio.months, portfolio.complete_through);
  container.appendChild(title);

  const chartCard = document.createElement('div');
  chartCard.className = 'card';
  const subjectLine = document.createElement('p');
  subjectLine.className = 'chart-subject';
  subjectLine.textContent = 'Written Amazon reviews per month, the only demand signal in this data.';
  chartCard.appendChild(subjectLine);
  const legend = document.createElement('div');
  legend.className = 'legend-row';
  legend.innerHTML = `
    <span class="legend-swatch"><span class="legend-dot" style="background:var(--graphite)"></span>New units</span>
    <span class="legend-swatch"><span class="legend-dot" style="background:var(--steel)"></span>Refurbished</span>
    <span>All Shark, Ninja and Euro-Pro products</span>
  `;
  chartCard.appendChild(legend);
  const chartStart = portfolio.chart_start || portfolio.months[0]?.m;
  const last = portfolio.months[portfolio.months.length - 1]?.m;
  chartCard.appendChild(renderVolumeChart({
    months: portfolio.months,
    from: chartStart,
    to: last,
    channels: { new: true, renewed: true },
    completeThrough: portfolio.complete_through,
    width: 1376,
    height: 260,
  }));
  if (portfolio.reviews_before_chart_start) {
    const beforeYear = Number(portfolio.months[0].m.slice(0, 4));
    const afterYear = Number(chartStart.slice(0, 4)) - 1;
    const note = document.createElement('p');
    note.className = 'field-note';
    note.style.margin = '4px 0 0 12px';
    const range = beforeYear === afterYear ? String(beforeYear) : `${beforeYear} to ${afterYear}`;
    note.textContent = `${range} hold ${intFmt(portfolio.reviews_before_chart_start)} reviews in total and are not drawn.`;
    chartCard.appendChild(note);
  }
  container.appendChild(chartCard);

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

  const sortState = { key: 'reviews_new', dir: 'desc' };

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
    for (const col of COLUMNS) {
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
    const col = COLUMNS.find((c) => c.key === sortState.key);
    h2.textContent = col.heading;
    const filterType = typeSelect.value;
    const rows = [...portfolio.families].filter((f) => !filterType || f.type === filterType);
    rows.sort((a, b) => {
      // Refurbished share is only meaningful with real new-unit volume: families with fewer than 50 new-unit
      // reviews (often refurbished-only listings) always sort to the bottom for that column.
      if (col.key === 'share') {
        const aw = a.reviews_new >= 50, bw = b.reviews_new >= 50;
        if (aw !== bw) return aw ? -1 : 1;
      }
      const av = col.accessor(a);
      const bv = col.accessor(b);
      let cmp;
      if (col.type === 'num') cmp = av - bv;
      else cmp = String(av).localeCompare(String(bv));
      return sortState.dir === 'asc' ? cmp : -cmp;
    });
    tbody.innerHTML = '';
    for (const f of rows) {
      const total = f.reviews_new + f.reviews_renewed;
      const share = total > 0 ? (f.reviews_renewed / total) * 100 : 0;
      const tr = document.createElement('tr');
      tr.tabIndex = 0;
      tr.setAttribute('role', 'button');
      tr.setAttribute('aria-label', `Open ${f.family}, ${humanizeType(f.type)}`);
      tr.innerHTML = `
        <td class="mono">${f.family}</td><td>${humanizeType(f.type)}</td>
        <td class="mono num">${intFmt(f.products)}</td>
        <td class="mono num">${intFmt(f.reviews_new)}</td>
        <td class="mono num">${intFmt(f.reviews_renewed)}</td>
        <td class="mono num">${share.toFixed(1)}%</td>
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
