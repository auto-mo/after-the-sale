import { loadPortfolio } from '../data.js?v=202609241634';
import { intFmt, decFmt, humanizeType } from '../format.js?v=202609241634';
import { renderCategoryLineChart, renderGroupedBarChart, cssVar } from '../charts.js?v=202609241634';

const BAND_ORDER = ['0 to 6 months', '7 to 12 months', 'Year 2', 'Years 3 to 4', 'Year 5+'];
const FAIL_BAND_ORDER = ['Under a month', '1 to 3 months', '4 to 11 months', 'About a year', '2 years or more'];
const ARRIVAL_KEYS = ['missing_parts', 'arrived_damaged_used', 'not_as_described', 'dead_on_arrival', 'stopped_working'];

function themeLabelMap(portfolio) {
  return new Map(portfolio.themes.map((t) => [t.key, t.label]));
}

function section(id, title) {
  const s = document.createElement('section');
  s.className = 'findings-section';
  s.id = id;
  const h2 = document.createElement('h2');
  h2.textContent = title;
  s.appendChild(h2);
  return s;
}

function caveat(text) {
  const p = document.createElement('p');
  p.className = 'findings-caveat';
  p.innerHTML = `<strong>Caveat.</strong> ${text}`;
  return p;
}

function seriesLegend(pairs) {
  const div = document.createElement('div');
  div.className = 'findings-legend';
  div.innerHTML = pairs.map(([label, color]) => `<span><i style="background:${color}"></i>${label}</span>`).join('');
  return div;
}

// #drift ------------------------------------------------------------------
function renderDrift(portfolio) {
  const f = portfolio.findings.drift;
  const s = section('drift', 'Ratings fall as products age, for every brand');
  const meta = document.createElement('p');
  meta.className = 'findings-meta';
  meta.textContent = `Same product, early versus later in its life (products with at least 100 reviews in both periods). SharkNinja: ${f.sharkninja.fell} of ${f.sharkninja.products} products rated lower in years 3 to 4 than in year 1 (average change ${decFmt(f.sharkninja.mean, 2)} stars). Peers: ${f.peers.fell} of ${f.peers.products} (average change ${decFmt(f.peers.mean, 2)} stars). For those same products, the share of 1 and 2-star reviews went from ${decFmt(f.sharkninja.low_year1 * 100, 0)}% in year 1 to ${decFmt(f.sharkninja.low_years3to4 * 100, 0)}% in years 3 to 4 for SharkNinja, and from ${decFmt(f.peers.low_year1 * 100, 0)}% to ${decFmt(f.peers.low_years3to4 * 100, 0)}% for peers. The chart averages every product with at least 30 reviews in each age band.`;
  s.appendChild(meta);

  const curve = portfolio.findings.curve;
  const byBand = (brand) => new Map(curve.filter((r) => r.brand_set === brand).map((r) => [r.age_band, r.rating]));
  const sn = byBand('SharkNinja');
  const pe = byBand('Peers');
  const bands = BAND_ORDER.filter((b) => sn.has(b) || pe.has(b));
  s.appendChild(renderCategoryLineChart({
    categories: bands,
    series: [
      { label: 'SharkNinja', color: cssVar('--graphite'), values: bands.map((b) => sn.get(b) ?? null) },
      { label: 'Peers', color: cssVar('--peer'), values: bands.map((b) => pe.get(b) ?? null) },
    ],
    yMin: 3, yMax: 5, yStep: 0.5, width: 760, height: 260, yFmt: (v) => decFmt(v, 1),
    ariaLabel: 'Average rating by product age, SharkNinja versus peers',
  }));
  s.appendChild(seriesLegend([['SharkNinja', 'var(--graphite)'], ['Peers', 'var(--peer)']]));
  s.appendChild(caveat('Later reviewers include owners whose unit already failed, so the fall is partly who is still reviewing, not only the product changing. Launch date is a proxy for some products.'));
  return s;
}

// #trend --------------------------------------------------------------------
function renderTrend(portfolio) {
  const s = section('trend', 'The rise in 1 and 2-star reviews is shared by peer brands');
  const rows = portfolio.findings.trend;
  const years = [...new Set(rows.map((r) => r.yr))].sort((a, b) => a - b);
  const byYear = (brand) => new Map(rows.filter((r) => r.brand_set === brand).map((r) => [r.yr, r.low_share]));
  const sn = byYear('SharkNinja');
  const pe = byYear('Peers');
  const meta = document.createElement('p');
  meta.className = 'findings-meta';
  const first = years[0];
  const last = years[years.length - 1];
  // 2015 to 2022: first year with steady volume in every compared type, and the last full year.
  meta.textContent = `By calendar year, across all products on sale: from 2015 to 2022, SharkNinja's 1 and 2-star share went from ${decFmt((sn.get(2015) || 0) * 100, 0)}% to ${decFmt((sn.get(2022) || 0) * 100, 0)}% and the peer brands' from ${decFmt((pe.get(2015) || 0) * 100, 0)}% to ${decFmt((pe.get(2022) || 0) * 100, 0)}%. ${last} covers January to March only.`;
  s.appendChild(meta);
  s.appendChild(renderCategoryLineChart({
    categories: years,
    series: [
      { label: 'SharkNinja', color: cssVar('--graphite'), values: years.map((y) => (sn.get(y) ?? null) === null ? null : sn.get(y) * 100) },
      { label: 'Peers', color: cssVar('--peer'), values: years.map((y) => (pe.get(y) ?? null) === null ? null : pe.get(y) * 100) },
    ],
    yMin: 0, yMax: 40, yStep: 10, width: 760, height: 260, yFmt: (v) => `${decFmt(v, 0)}%`,
    dashedFrom: years.length - 1,
    ariaLabel: '1 and 2-star review share by year, SharkNinja versus peers',
  }));
  s.appendChild(seriesLegend([['SharkNinja', 'var(--graphite)'], ['Peers', 'var(--peer)'], [`${last} is partial (Q1 only), shown dashed`, 'var(--hairline)']]));
  s.appendChild(caveat('Each product type counts equally within each brand set, in both SharkNinja and peers. Peers are five brands, not all of Amazon.'));
  return s;
}

// #complaints -----------------------------------------------------------
function renderComplaints(portfolio, labels) {
  const s = section('complaints', 'Each category has a signature complaint');
  const p = document.createElement('p');
  p.className = 'findings-explain';
  p.textContent = 'For each product type, the three complaints with the widest gap between SharkNinja and peer-brand owners.';
  s.appendChild(p);

  const group = document.createElement('div');
  group.className = 'dumbbell-group';
  const maxShare = Math.max(0.02, ...portfolio.types.flatMap((t) => (t.biggest_gap || []).flatMap((g) => [g.sn || 0, g.peers || 0])));
  for (const t of portfolio.types) {
    if (!t.biggest_gap || !t.biggest_gap.length) continue;
    const wrap = document.createElement('div');
    const title = document.createElement('div');
    title.className = 'dumbbell-type';
    title.textContent = `${humanizeType(t.type)} (vs ${t.peer_brands.join(', ') || 'peers'})`;
    wrap.appendChild(title);
    for (const g of t.biggest_gap) {
      const row = document.createElement('div');
      row.className = 'dumbbell-row';
      const snPct = (g.sn || 0) / maxShare * 100;
      const peerPct = (g.peers || 0) / maxShare * 100;
      const lo = Math.min(snPct, peerPct);
      const hi = Math.max(snPct, peerPct);
      row.innerHTML = `
        <span class="dumbbell-label">${labels.get(g.theme) || g.theme}</span>
        <span class="dumbbell-track">
          <span class="dumbbell-connector" style="left:${lo}%;width:${hi - lo}%"></span>
          <span class="dumbbell-dot sn" style="left:${snPct}%"></span>
          <span class="dumbbell-dot peer" style="left:${peerPct}%"></span>
        </span>
        <span class="dumbbell-values">${decFmt((g.sn || 0) * 100, 1)}% vs ${decFmt((g.peers || 0) * 100, 1)}%</span>
      `;
      wrap.appendChild(row);
    }
    group.appendChild(wrap);
  }
  s.appendChild(group);
  s.appendChild(seriesLegend([['SharkNinja', 'var(--graphite)'], ['Peers', 'var(--peer)']]));
  s.appendChild(caveat('These are keyword-matched themes, not verified failures. Measured precision by theme is on the Method page.'));
  return s;
}

// #failure ----------------------------------------------------------------
function renderFailure(portfolio) {
  const s = section('failure', 'When owners say it stopped working');
  const bands = portfolio.findings.fail.bands.filter((b) => b.product_type === 'All types');
  const byBrand = (brand) => new Map(bands.filter((b) => b.brand_set === brand).map((b) => [b.fail_band, b.n]));
  const sn = byBrand('SharkNinja');
  const pe = byBrand('Peers');
  const snTotal = [...sn.values()].reduce((a, b) => a + b, 0);
  const peTotal = [...pe.values()].reduce((a, b) => a + b, 0);
  const p = document.createElement('p');
  p.className = 'findings-explain';
  p.textContent = `Share of stated failure times in each band, out of ${intFmt(snTotal)} SharkNinja and ${intFmt(peTotal)} peer reviews that named a time.`;
  s.appendChild(p);
  s.appendChild(renderGroupedBarChart({
    categories: FAIL_BAND_ORDER,
    series: [
      { label: 'SharkNinja', color: cssVar('--graphite'), values: FAIL_BAND_ORDER.map((b) => (snTotal ? ((sn.get(b) || 0) / snTotal) * 100 : 0)) },
      { label: 'Peers', color: cssVar('--peer'), values: FAIL_BAND_ORDER.map((b) => (peTotal ? ((pe.get(b) || 0) / peTotal) * 100 : 0)) },
    ],
    width: 760, height: 260, valueFmt: (v) => `${decFmt(v, 1)}%`, yFmt: (v) => `${intFmt(v)}%`, ariaLabel: 'Stated time to failure, SharkNinja versus peers',
  }));
  s.appendChild(seriesLegend([['SharkNinja', 'var(--graphite)'], ['Peers', 'var(--peer)']]));

  // Medians by type, only for the types compared with peer brands, side by side.
  const med = (set, t) => portfolio.findings.fail.summary.find((r) => r.brand_set === set && r.product_type === t);
  const table = document.createElement('table');
  table.className = 'year-table';
  table.innerHTML = '<thead><tr><th>Type</th><th class="num">SharkNinja, median months</th><th class="num">Peers, median months</th></tr></thead>';
  const tbody = document.createElement('tbody');
  for (const t of portfolio.types) {
    const a = med('SharkNinja', t.type);
    const b = med('Peers', t.type);
    if (!a || !b) continue;
    const cell = (r) => `${decFmt(r.median_months, 0)} <span class="few-note">(${intFmt(r.n)} reviews)</span>`;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${humanizeType(t.type)}</td><td class="mono num">${cell(a)}</td><td class="mono num">${cell(b)}</td>`;
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  s.appendChild(table);
  s.appendChild(caveat('Owners round to familiar numbers such as 6, 12 and 24 months. Only reviews that state a time are counted.'));
  return s;
}

// #refurb -------------------------------------------------------------------
function renderRefurb(portfolio, labels) {
  const r = portfolio.findings.refurb;
  const s = section('refurb', 'Refurbished units hold up; what goes wrong is on arrival');
  const meta = document.createElement('p');
  meta.className = 'findings-meta';
  meta.textContent = `Comparing the same product in the same year (${intFmt(r.cells)} product-years across ${intFmt(r.products)} products): an average gap of ${decFmt(r.mean_gap, 2)} stars, with refurbished rated lower in ${decFmt(r.lower_share * 100, 0)}% of them. Comparing all reviews with no such matching, refurbished averages ${decFmt(r.naive_refurb, 2)} against ${decFmt(r.naive_new, 2)} for new, a wider gap driven mostly by which products end up refurbished.`;
  s.appendChild(meta);

  const p = document.createElement('p');
  p.className = 'findings-explain';
  p.textContent = 'The clearest differences show up on arrival: missing parts, damage or signs of use. Stopped working is shown for contrast; it is lower for refurbished, partly because those reviews are written sooner after purchase.';
  s.appendChild(p);

  const cats = Object.keys(r.arrival);
  s.appendChild(renderGroupedBarChart({
    categories: cats.map((k) => labels.get(k) || k),
    series: [
      { label: 'New', color: cssVar('--graphite'), values: cats.map((k) => (r.arrival[k].new || 0) * 100) },
      { label: 'Refurbished', color: cssVar('--steel'), values: cats.map((k) => (r.arrival[k].refurbished || 0) * 100) },
    ],
    width: 760, height: 260, valueFmt: (v) => `${decFmt(v, 1)}%`, yFmt: (v) => `${intFmt(v)}%`, ariaLabel: 'Arrival complaints, new versus refurbished',
  }));
  s.appendChild(seriesLegend([['New', 'var(--graphite)'], ['Refurbished', 'var(--steel)']]));
  s.appendChild(caveat('Refurbished reviews are fewer and skew later in a product’s life, so the comparison rests on a smaller, less representative sample.'));
  return s;
}

// #cases ----------------------------------------------------------------
function renderCases(portfolio, labels) {
  const s = section('cases', 'Products whose complaints jumped in one year');
  const p = document.createElement('p');
  p.className = 'findings-explain';
  p.textContent = 'The largest one-year rises in 1 and 2-star share, compared with how peers moved in the same type and year. This is descriptive: the data cannot say why.';
  s.appendChild(p);

  const list = document.createElement('div');
  list.className = 'case-list';
  for (const c of portfolio.findings.cases) {
    const row = document.createElement('div');
    row.className = 'case-row';
    const rising = (c.rising || []).map((r) => labels.get(r.theme) || r.theme).join(', ');
    row.innerHTML = `
      <div class="case-info">
        <span class="case-model"><a href="#/product/${c.product_id}">${c.label}</a> &middot; ${humanizeType(c.type)}</span>
        <span class="case-sub">${c.prev_year ?? '–'} to ${c.year}: 1 and 2-star share ${decFmt((c.prev_low_share || 0) * 100, 0)}% to ${decFmt(c.low_share * 100, 0)}% (peer brands moved ${decFmt(Math.abs(c.peers_change || 0) * 100, 0) === '0' ? 'about 0' : `${c.peers_change > 0 ? '+' : '-'}${decFmt(Math.abs(c.peers_change) * 100, 0)}`} points that year)</span>
        ${rising ? `<span class="case-rising">Rising: ${rising}</span>` : ''}
      </div>
      <div class="case-change">
        <span class="case-change-value">+${decFmt(c.excess * 100, 0)} pts</span>
        <span class="case-change-note">excess vs peers</span>
      </div>
    `;
    list.appendChild(row);
  }
  s.appendChild(list);
  s.appendChild(caveat('These are the largest one-year rises in the data, and the data cannot say what caused any of them. Treat each as a lead to look into, not a conclusion.'));
  return s;
}

function scrollToAnchor() {
  const hash = window.location.hash || '';
  const q = hash.split('?')[1];
  if (!q) return;
  const anchor = new URLSearchParams(q).get('anchor');
  if (!anchor) return;
  const el = document.getElementById(anchor);
  if (el) el.scrollIntoView({ block: 'start', behavior: 'auto' });
}

export async function render(container) {
  container.innerHTML = '<div class="empty-state">Loading findings…</div>';
  let portfolio;
  try {
    portfolio = await loadPortfolio();
  } catch (err) {
    container.innerHTML = `<div class="error-state">Could not load findings data. ${err.message}</div>`;
    return;
  }
  const labels = themeLabelMap(portfolio);
  container.innerHTML = '';

  const h1 = document.createElement('h1');
  h1.style.marginBottom = '18px';
  h1.textContent = 'What the data shows, and where it stops';
  container.appendChild(h1);

  container.appendChild(renderDrift(portfolio));
  container.appendChild(renderTrend(portfolio));
  container.appendChild(renderComplaints(portfolio, labels));
  container.appendChild(renderFailure(portfolio));
  container.appendChild(renderRefurb(portfolio, labels));
  container.appendChild(renderCases(portfolio, labels));

  requestAnimationFrame(scrollToAnchor);
}
