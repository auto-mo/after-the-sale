import { loadPortfolio, loadProducts } from '../data.js?v=202609232309';
import { renderVolumeChart } from '../charts.js?v=202609232309';
import { intFmt, monthLong, humanizeType } from '../format.js?v=202609232309';
import { setView } from '../state.js?v=202609232309';
import { navigate } from '../router.js?v=202609232309';

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
  const [cy, cm] = completeThrough.split('-');
  const monthName = monthLong(completeThrough);
  return `Review volume grew about ${ratioText} from ${startYear} to ${endYear}; data thins after ${monthName}`;
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
  const legend = document.createElement('div');
  legend.className = 'legend-row';
  legend.innerHTML = `
    <span class="legend-swatch"><span class="legend-dot" style="background:var(--graphite)"></span>New units</span>
    <span class="legend-swatch"><span class="legend-dot" style="background:var(--steel)"></span>Refurbished</span>
    <span>All Shark, Ninja and Euro-Pro products, reviews per month</span>
  `;
  chartCard.appendChild(legend);
  const first = portfolio.months[0]?.m;
  const last = portfolio.months[portfolio.months.length - 1]?.m;
  chartCard.appendChild(renderVolumeChart({
    months: portfolio.months,
    from: first,
    to: last,
    channels: { new: true, renewed: true },
    completeThrough: portfolio.complete_through,
    width: 1376,
    height: 260,
  }));
  container.appendChild(chartCard);

  const head = document.createElement('div');
  head.className = 'families-head';
  const h2 = document.createElement('h2');
  h2.textContent = 'Largest product families by review volume';
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
  table.innerHTML = `
    <thead><tr>
      <th scope="col">Family</th><th scope="col">Main type</th>
      <th scope="col" class="num">Products</th><th scope="col" class="num">New-unit reviews</th>
      <th scope="col" class="num">Refurbished reviews</th><th scope="col" class="num">Refurbished share</th>
    </tr></thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector('tbody');

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

  function drawTable() {
    const filterType = typeSelect.value;
    const rows = [...portfolio.families]
      .filter((f) => !filterType || f.type === filterType)
      .sort((a, b) => (b.reviews_new + b.reviews_renewed) - (a.reviews_new + a.reviews_renewed));
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
  drawTable();

  tableWrap.appendChild(table);
  container.appendChild(tableWrap);
}
