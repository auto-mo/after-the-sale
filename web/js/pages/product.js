import { loadProductDetail, loadPortfolio } from '../data.js?v=202609241634';
import {
  renderVolumeChart, renderRatingStrip, renderRatingMainChart, renderVolumeStrip, monthsInRange,
  renderCategoryLineChart, renderGroupedBarChart, cssVar,
} from '../charts.js?v=202609241634';
import {
  intFmt, decFmt, monthShort, monthLong, dateShort, monthIndex, humanizeLaunchSource, humanizeType, EMPTY,
} from '../format.js?v=202609241634';
import { view, setView, onViewChanged } from '../state.js?v=202609241634';

const BAND_ORDER = ['0 to 6 months', '7 to 12 months', 'Year 2', 'Years 3 to 4', 'Year 5+'];
const ARRIVAL_KEYS = ['missing_parts', 'arrived_damaged_used', 'not_as_described', 'dead_on_arrival'];

function themeLabelMap(portfolio) {
  return new Map(portfolio.themes.map((t) => [t.key, t.label]));
}

function buildMeta(product) {
  const bits = [];
  bits.push(`model ${product.model || product.id}`);
  if (product.family) bits.push(`family ${product.family}`);
  bits.push(`launched ${dateShort(product.launch)} (${humanizeLaunchSource(product.launch_source)})`);
  const refurb = product.renewed || 0;
  const brandStore = product.brand_store || 0;
  bits.push(`${intFmt(product.listings)} listing${product.listings === 1 ? '' : 's'} (${intFmt(brandStore)} brand store, ${intFmt(refurb)} refurbished)`);
  bits.push(`${intFmt(product.reviews_new)} new-unit reviews`);
  bits.push(`${intFmt(product.reviews_renewed)} refurbished`);
  if (product.rating_new !== null && product.rating_new !== undefined) bits.push(`avg rating ${decFmt(product.rating_new, 2)}`);
  return bits;
}

function computeVolumeTakeaway(months, from, to, channels) {
  const data = monthsInRange(months, from, to);
  let best = null;
  for (const row of data) {
    const total = (channels.new ? row.new || 0 : 0) + (channels.renewed ? row.renewed || 0 : 0);
    if (!best || total > best.total) best = { total, m: row.m };
  }
  if (!best || best.total === 0) return 'No reviews in the selected window';
  return `Reviews peaked at ${intFmt(best.total)} in ${monthLong(best.m)}`;
}

// Monthly averages from a handful of reviews swing between 1 and 5 and read as signal; plot a month only
// when it has at least MIN_MONTH_REVIEWS reviews in that channel.
const MIN_MONTH_REVIEWS = 5;
function ratingMonths(months) {
  return months.map((r) => ({
    ...r,
    rating_new: (r.new || 0) >= MIN_MONTH_REVIEWS ? r.rating_new : null,
    rating_renewed: (r.renewed || 0) >= MIN_MONTH_REVIEWS ? r.rating_renewed : null,
  }));
}

/** Headline for the rating view: the most recent one-year rise in the 1 and 2-star share inside the window
 * (10+ points, 100+ reviews in both years), otherwise the window's average rating. */
function computeRatingTakeaway(detail, from, to) {
  const y0 = Number(from.slice(0, 4));
  const y1 = Number(to.slice(0, 4));
  const years = (detail.years || []).filter((y) => y.yr >= y0 && y.yr <= y1);
  let best = null;
  for (let i = 1; i < years.length; i += 1) {
    const a = years[i - 1];
    const b = years[i];
    // Complete years only: the data ends in March 2023, so 2023 is a partial year.
    if (b.yr !== a.yr + 1 || b.yr > 2022 || a.n < 100 || b.n < 100) continue;
    const jump = b.low_share - a.low_share;
    if (jump >= 0.10) best = { a, b, jump }; // the most recent qualifying rise wins; recent changes matter most
  }
  if (best) {
    return `The share of 1 and 2-star reviews rose from ${decFmt(best.a.low_share * 100, 0)}% in ${best.a.yr} to ${decFmt(best.b.low_share * 100, 0)}% in ${best.b.yr}`;
  }
  const data = monthsInRange(detail.months, from, to);
  let n = 0;
  let sum = 0;
  for (const r of data) {
    if (r.rating_new !== null && r.rating_new !== undefined && r.new) { n += r.new; sum += r.rating_new * r.new; }
  }
  if (!n) return 'No new-unit ratings in the selected window';
  return `New units averaged ${decFmt(sum / n, 2)} stars across ${intFmt(n)} reviews in this window`;
}

function windowTotals(months, from, to) {
  const data = monthsInRange(months, from, to);
  let newTotal = 0;
  let renewedTotal = 0;
  for (const row of data) {
    newTotal += row.new || 0;
    renewedTotal += row.renewed || 0;
  }
  return { new: newTotal, renewed: renewedTotal, total: newTotal + renewedTotal };
}

// ---- "What owners report" rail sections ----

function renderComplaintMix(rail, product, detail, labels) {
  const section = document.createElement('section');
  section.className = 'rail-section';
  const th = detail.themes;

  if (!th || !th.shown) {
    const h2 = document.createElement('h2');
    h2.textContent = 'What owners report';
    section.appendChild(h2);
    const note = document.createElement('p');
    note.className = 'rail-intro';
    note.textContent = 'Fewer than 30 low-star reviews, so no complaint breakdown.';
    section.appendChild(note);
    rail.appendChild(section);
    return;
  }

  const shares = th.shares;
  const rows = Object.keys(shares)
    .filter((k) => k !== 'warranty_service' && shares[k] !== null && shares[k] !== undefined)
    .sort((a, b) => shares[b] - shares[a])
    .slice(0, 6);

  const top = rows[0];
  const topShare = shares[top];
  const peerShare = th.type_peers ? th.type_peers.shares[top] : null;
  let headline = 'Owners report a spread of complaints, none dominant';
  if (top && topShare > 0) {
    if (peerShare && peerShare > 0) {
      const ratio = topShare / peerShare;
      headline = ratio >= 1.3
        ? `${labels.get(top) || top} leads complaints, ${decFmt(ratio, 1)}x the peer rate`
        : ratio <= 0.77
          ? `${labels.get(top) || top} leads complaints, below the peer rate`
          : `${labels.get(top) || top} leads complaints, close to the peer rate`;
    } else {
      headline = `${labels.get(top) || top} leads complaints`;
    }
  }

  const h2 = document.createElement('h2');
  h2.textContent = 'What owners report';
  section.appendChild(h2);
  const h3 = document.createElement('h3');
  h3.textContent = headline;
  section.appendChild(h3);

  const maxScale = Math.max(0.05, ...rows.map((k) => shares[k] || 0),
    ...(th.type_sharkninja ? rows.map((k) => th.type_sharkninja.shares[k] || 0) : []),
    ...(th.type_peers ? rows.map((k) => th.type_peers.shares[k] || 0) : []));

  const bars = document.createElement('div');
  bars.className = 'complaint-bars';
  for (const k of rows) {
    const row = document.createElement('div');
    row.className = 'complaint-row';
    const pct = (shares[k] || 0) / maxScale * 100;
    const snPct = th.type_sharkninja ? (th.type_sharkninja.shares[k] || 0) / maxScale * 100 : null;
    const peerPct = th.type_peers ? (th.type_peers.shares[k] || 0) / maxScale * 100 : null;
    row.innerHTML = `
      <div class="complaint-row-head"><span class="cr-label">${labels.get(k) || k}</span><span class="cr-value mono">${decFmt((shares[k] || 0) * 100, 1)}%</span></div>
      <div class="complaint-track">
        <div class="complaint-fill" style="width:${pct}%"></div>
        ${snPct !== null ? `<div class="complaint-marker sn" style="left:${snPct}%" title="SharkNinja ${humanizeType(product.type)} average"></div>` : ''}
        ${peerPct !== null ? `<div class="complaint-marker peer" style="left:${peerPct}%" title="Peer average"></div>` : ''}
      </div>
    `;
    bars.appendChild(row);
  }
  section.appendChild(bars);

  const legend = document.createElement('div');
  legend.className = 'complaint-legend';
  const peerNames = th.type_peers && th.type_peers.brands && th.type_peers.brands.length ? th.type_peers.brands.join(', ') : 'peers';
  legend.innerHTML = `
    <span><i style="background:var(--graphite)"></i>${humanizeType(product.type)} product</span>
    <span><i style="background:var(--steel)"></i>SharkNinja ${humanizeType(product.type)} average</span>
    <span><i style="background:var(--peer)"></i>${peerNames} average</span>
  `;
  section.appendChild(legend);
  rail.appendChild(section);

  if (th.top && th.top.length) renderThemeQuotes(rail, th.top, labels);
}

function quoteCard(q) {
  const card = document.createElement('div');
  card.className = 'quote-card';
  const meta = document.createElement('div');
  meta.className = 'quote-meta';
  const bits = [dateShort(q.date), `${q.rating}★`];
  if (q.verified) bits.push('verified');
  if (q.helpful) bits.push(`${intFmt(q.helpful)} found helpful`);
  bits.forEach((b) => {
    const s = document.createElement('span');
    s.textContent = b;
    meta.appendChild(s);
  });
  card.appendChild(meta);
  const text = document.createElement('p');
  text.className = 'quote-text';
  text.textContent = q.text; // user text: textContent only, never innerHTML
  card.appendChild(text);
  return card;
}

function renderThemeQuotes(rail, top, labels) {
  const section = document.createElement('section');
  section.className = 'rail-section';
  const h3 = document.createElement('h3');
  h3.textContent = 'In their words';
  section.appendChild(h3);

  const [first, ...rest] = top;
  const firstBlock = document.createElement('div');
  firstBlock.className = 'theme-block';
  firstBlock.innerHTML = `<div class="theme-block-head"><span>${labels.get(first.theme) || first.theme}</span><span class="tb-share mono">${decFmt(first.share * 100, 1)}%</span></div>`;
  first.quotes.forEach((q) => firstBlock.appendChild(quoteCard(q)));
  section.appendChild(firstBlock);

  if (rest.length) {
    const details = document.createElement('details');
    details.className = 'theme-quotes-more';
    const summary = document.createElement('summary');
    summary.textContent = `${rest.length} more complaint theme${rest.length === 1 ? '' : 's'} with quotes`;
    details.appendChild(summary);
    for (const t of rest) {
      const block = document.createElement('div');
      block.className = 'theme-block';
      block.innerHTML = `<div class="theme-block-head"><span>${labels.get(t.theme) || t.theme}</span><span class="tb-share mono">${decFmt(t.share * 100, 1)}%</span></div>`;
      t.quotes.forEach((q) => block.appendChild(quoteCard(q)));
      details.appendChild(block);
    }
    section.appendChild(details);
  }
  rail.appendChild(section);
}

function renderYearTable(rail, detail, labels) {
  if (!detail.years || !detail.years.length) return;
  const section = document.createElement('section');
  section.className = 'rail-section';
  const h3 = document.createElement('h3');
  h3.textContent = 'Year by year';
  section.appendChild(h3);

  const table = document.createElement('table');
  table.className = 'year-table';
  table.innerHTML = '<thead><tr><th>Year</th><th class="num">Reviews</th><th class="num">1 and 2-star share</th><th>Most common complaint</th></tr></thead>';
  const tbody = document.createElement('tbody');
  const sorted = [...detail.years].sort((a, b) => a.yr - b.yr);
  sorted.forEach((y, i) => {
    const prev = sorted[i - 1];
    // Same rule as the headline: consecutive years, 100+ reviews in both, a rise of 10 points or more.
    const rose = prev && prev.yr === y.yr - 1 && y.yr <= 2022 && prev.n >= 100 && y.n >= 100 && prev.low_share !== null && y.low_share !== null && (y.low_share - prev.low_share) >= 0.10;
    const tr = document.createElement('tr');
    if (rose) tr.className = 'year-rise';
    const yearLabel = y.yr === 2023 ? '2023 (Jan-Mar)' : String(y.yr);
    const complaint = y.top_theme ? (labels.get(y.top_theme) || y.top_theme) : (y.n_low < 15 ? 'Too few low-star reviews' : EMPTY);
    tr.innerHTML = `<td class="mono">${yearLabel}</td><td class="mono num">${intFmt(y.n)}</td><td class="mono num">${decFmt(y.low_share * 100, 1)}%</td><td>${complaint}</td>`;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  section.appendChild(table);
  rail.appendChild(section);
}

function renderLifecycle(rail, detail) {
  if (!detail.lifecycle || !detail.lifecycle.length) return;
  const section = document.createElement('section');
  section.className = 'rail-section';
  const h3 = document.createElement('h3');
  h3.textContent = "Over the product's life";
  section.appendChild(h3);

  // Bands with fewer than 30 reviews are left out, the same floor the type averages use.
  const byBand = new Map(detail.lifecycle.filter((r) => r.n >= 30).map((r) => [r.age_band, r.rating]));
  const snRef = new Map((detail.lifecycle_ref || []).filter((r) => r.brand_set === 'SharkNinja').map((r) => [r.age_band, r.rating]));
  const peerRef = new Map((detail.lifecycle_ref || []).filter((r) => r.brand_set === 'Peers').map((r) => [r.age_band, r.rating]));
  const bands = BAND_ORDER.filter((b) => byBand.has(b) || snRef.has(b) || peerRef.has(b));

  const series = [
    { label: 'This product', color: cssVar('--graphite'), values: bands.map((b) => byBand.get(b) ?? null) },
    { label: 'SharkNinja average', color: cssVar('--steel'), values: bands.map((b) => snRef.get(b) ?? null) },
    { label: 'Peer average', color: cssVar('--peer'), values: bands.map((b) => peerRef.get(b) ?? null) },
  ];
  const vals = series.flatMap((x) => x.values).filter((v) => v !== null);
  const yMin = Math.min(3, Math.floor(Math.min(...vals) * 2) / 2);
  section.appendChild(renderCategoryLineChart({
    categories: bands, series, yMin, yMax: 5, yStep: 0.5, width: 900, height: 240,
    yFmt: (v) => decFmt(v, 1), ariaLabel: 'Average rating by product age',
  }));
  const legend = document.createElement('div');
  legend.className = 'complaint-legend';
  legend.innerHTML = `
    <span><i style="background:var(--graphite)"></i>This product</span>
    <span><i style="background:var(--steel)"></i>SharkNinja average</span>
    <span><i style="background:var(--peer)"></i>Peer average</span>
  `;
  section.appendChild(legend);

  if (detail.drift) {
    const p = document.createElement('p');
    p.className = 'lifecycle-note';
    p.textContent = `Rated ${decFmt(detail.drift.r1, 2)} in year 1 and ${decFmt(detail.drift.r3, 2)} in years 3 to 4.`;
    section.appendChild(p);
  }
  if (detail.launch_source && detail.launch_source.includes('first review')) {
    const p = document.createElement('p');
    p.className = 'lifecycle-note';
    p.textContent = detail.launch_source.includes('earlier than listed')
      ? 'Product age counts from the first review, which came before the listed first-available date.'
      : 'Product age counts from the first review, since no listed first-available date exists.';
    section.appendChild(p);
  }
  rail.appendChild(section);
}

function renderRefurb(rail, detail, portfolio) {
  if (!detail.refurb) return;
  const r = detail.refurb;
  const section = document.createElement('section');
  section.className = 'rail-section';
  const h3 = document.createElement('h3');
  h3.textContent = 'Refurbished';
  section.appendChild(h3);

  const nc = r.channels.new;
  const rc = r.channels.refurbished;
  const summary = document.createElement('div');
  summary.className = 'refurb-summary';
  summary.innerHTML = `
    <div class="stat-tile"><span class="stat-label">New rating</span><span class="stat-value mono">${decFmt(nc.rating, 2)}</span><span class="stat-note">${decFmt(nc.low_share * 100, 1)}% 1 and 2-star (${intFmt(nc.n)} reviews)</span></div>
    <div class="stat-tile"><span class="stat-label">Refurbished rating</span><span class="stat-value mono">${decFmt(rc.rating, 2)}</span><span class="stat-note">${decFmt(rc.low_share * 100, 1)}% 1 and 2-star (${intFmt(rc.n)} reviews)</span></div>
  `;
  section.appendChild(summary);

  if (r.cells && r.cells.length) {
    const table = document.createElement('table');
    table.className = 'refurb-cells';
    table.innerHTML = '<thead><tr><th>Year</th><th>New</th><th>Refurbished</th><th>Gap</th></tr></thead>';
    const tbody = document.createElement('tbody');
    for (const c of r.cells) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${c.yr}</td><td class="mono">${decFmt(c.r_new, 2)} (${intFmt(c.n_new)})</td><td class="mono">${decFmt(c.r_ref, 2)} (${intFmt(c.n_ref)})</td><td class="mono">${decFmt(c.gap, 2)}</td>`;
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    const p = document.createElement('p');
    p.className = 'lifecycle-note';
    p.textContent = 'Same product, same year: refurbished versus new.';
    section.appendChild(p);
    section.appendChild(table);
  }

  const arrivalNew = ARRIVAL_KEYS.map((k) => nc.shares[k] || 0);
  const arrivalRef = ARRIVAL_KEYS.map((k) => rc.shares[k] || 0);
  if (rc.n_low < 30) {
    const p = document.createElement('p');
    p.className = 'lifecycle-note';
    p.textContent = `Only ${intFmt(rc.n_low)} low-star refurbished reviews, too few for an arrival-complaint breakdown.`;
    section.appendChild(p);
  } else if (arrivalNew.some((v) => v > 0) || arrivalRef.some((v) => v > 0)) {
    const p = document.createElement('p');
    p.className = 'lifecycle-note';
    p.textContent = 'Arrival complaints, share of low-star reviews:';
    section.appendChild(p);
    section.appendChild(renderGroupedBarChart({
      categories: ARRIVAL_KEYS.map((k) => (portfolio.themes.find((t) => t.key === k) || {}).label || k),
      series: [
        { label: 'New', color: cssVar('--graphite'), values: arrivalNew.map((v) => v * 100) },
        { label: 'Refurbished', color: cssVar('--steel'), values: arrivalRef.map((v) => v * 100) },
      ],
      width: 640, height: 220, valueFmt: (v) => `${decFmt(v, 1)}%`, yFmt: (v) => `${intFmt(v)}%`, ariaLabel: 'Arrival complaints, new versus refurbished',
    }));
  }

  if (r.quotes && r.quotes.length) {
    const p = document.createElement('p');
    p.className = 'lifecycle-note';
    p.textContent = 'From refurbished-unit reviews:';
    section.appendChild(p);
    r.quotes.slice(0, 3).forEach((q) => section.appendChild(quoteCard(q)));
  }

  rail.appendChild(section);
}

export async function render(container, params) {
  const id = params.id || view.productId;
  setView({ productId: id });
  container.innerHTML = '<div class="empty-state">Loading product…</div>';

  let result, portfolio;
  try {
    [result, portfolio] = await Promise.all([loadProductDetail(id), loadPortfolio()]);
  } catch (err) {
    container.innerHTML = `<div class="error-state">Could not load this product's data. ${err.message}</div>`;
    return;
  }

  if (result.notFound || !result.product) {
    container.innerHTML = '<div class="error-state">This product does not exist in the data.</div>';
    return;
  }

  const { product, detail } = result;
  const labels = themeLabelMap(portfolio);

  container.innerHTML = '';
  const layout = document.createElement('div');
  layout.className = 'product-layout';
  container.appendChild(layout);

  const main = document.createElement('section');
  main.className = 'product-main';
  layout.appendChild(main);

  const heading = document.createElement('div');
  heading.className = 'product-heading';
  const h1 = document.createElement('h1');
  h1.textContent = `${product.brand} ${product.model || ''} ${humanizeType(product.type)}`.replace(/\s+/g, ' ').trim();
  heading.appendChild(h1);
  const meta = document.createElement('div');
  meta.className = 'product-meta';
  meta.innerHTML = buildMeta(product).map((b) => `<span>${b}</span>`).join('');
  heading.appendChild(meta);
  main.appendChild(heading);

  if (!detail) {
    const empty = document.createElement('div');
    empty.className = 'card empty-state';
    empty.textContent = 'No reviews for this product in the data.';
    main.appendChild(empty);
    return;
  }

  const firstMonth = detail.months[0].m;
  const lastMonth = detail.months[detail.months.length - 1].m;
  const defaultTo = monthIndex(portfolio.complete_through) <= monthIndex(lastMonth) ? portfolio.complete_through : lastMonth;
  if (!view.from || monthIndex(view.from) < monthIndex(firstMonth) || monthIndex(view.from) > monthIndex(lastMonth)) view.from = firstMonth;
  if (!view.to || monthIndex(view.to) < monthIndex(firstMonth) || monthIndex(view.to) > monthIndex(lastMonth)) view.to = defaultTo;

  // ---- controls row ----
  const controls = document.createElement('div');
  controls.className = 'controls-row';
  main.appendChild(controls);

  const fieldset = document.createElement('fieldset');
  fieldset.className = 'controls-fieldset';
  fieldset.innerHTML = `
    <legend>Show</legend>
    <label class="channel-check" for="ch-new"><input id="ch-new" type="checkbox" checked><span class="channel-swatch" style="background:var(--graphite)"></span>New units</label>
    <label class="channel-check" for="ch-ref"><input id="ch-ref" type="checkbox" checked><span class="channel-swatch" style="background:var(--steel)"></span>Refurbished</label>
  `;
  controls.appendChild(fieldset);
  const chNew = fieldset.querySelector('#ch-new');
  const chRef = fieldset.querySelector('#ch-ref');
  chNew.checked = view.channels.new;
  chRef.checked = view.channels.renewed;

  const hint = document.createElement('span');
  hint.className = 'hint-text';
  hint.style.margin = '0';
  hint.hidden = true;
  hint.textContent = 'At least one of New units or Refurbished must stay checked.';

  const monthOptions = detail.months.map((m) => m.m);
  const rangeGroup = document.createElement('div');
  rangeGroup.className = 'range-group';
  const optHtml = (selected) => monthOptions.map((m) => `<option value="${m}"${m === selected ? ' selected' : ''}>${monthShort(m)}${monthIndex(m) > monthIndex(portfolio.complete_through) ? ' (partial)' : ''}</option>`).join('');
  rangeGroup.innerHTML = `
    <label for="from-sel">From</label><select id="from-sel">${optHtml(view.from)}</select>
    <label for="to-sel">To</label><select id="to-sel">${optHtml(view.to)}</select>
  `;
  controls.appendChild(rangeGroup);
  const fromSel = rangeGroup.querySelector('#from-sel');
  const toSel = rangeGroup.querySelector('#to-sel');

  const switchGroup = document.createElement('div');
  switchGroup.className = 'switch-group';
  switchGroup.innerHTML = `
    <span id="measure-rat-label" class="switch-label-on">Rating</span>
    <button type="button" id="measure-switch" class="switch" role="switch" aria-checked="false" aria-labelledby="measure-rat-label measure-vol-label"></button>
    <span id="measure-vol-label">Volume</span>
  `;
  switchGroup.querySelector('.switch').innerHTML =
    '<span class="switch-knob"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M7 7h11l-3-3M17 17H6l3 3"/></svg></span>';
  controls.appendChild(switchGroup);
  const measureSwitch = switchGroup.querySelector('#measure-switch');
  const ratLabel = switchGroup.querySelector('#measure-rat-label');
  const volLabel = switchGroup.querySelector('#measure-vol-label');

  // ---- chart card ----
  const chartCard = document.createElement('div');
  chartCard.className = 'card chart-card';
  main.appendChild(chartCard);

  const chartTitle = document.createElement('h2');
  chartCard.appendChild(chartTitle);
  const subjectLine = document.createElement('p');
  subjectLine.className = 'chart-subject';
  chartCard.appendChild(subjectLine);
  const legend = document.createElement('div');
  legend.className = 'legend-row';
  chartCard.appendChild(legend);
  const refurbNote = document.createElement('p');
  refurbNote.className = 'field-note';
  refurbNote.style.margin = '0 0 0 12px';
  refurbNote.hidden = true;
  chartCard.appendChild(refurbNote);
  const mainChartHolder = document.createElement('div');
  chartCard.appendChild(mainChartHolder);
  chartCard.appendChild(hint);

  const ratingHead = document.createElement('div');
  ratingHead.className = 'rating-row-head';
  chartCard.appendChild(ratingHead);
  const rrTitle = document.createElement('span');
  rrTitle.className = 'rr-title';
  const rrNote = document.createElement('span');
  rrNote.className = 'rr-note';
  rrNote.innerHTML = '<span class="rr-dot"></span>months below 4.4';
  ratingHead.appendChild(rrTitle);
  ratingHead.appendChild(rrNote);
  const secondaryChartHolder = document.createElement('div');
  chartCard.appendChild(secondaryChartHolder);

  function updateLegend(channels, totals) {
    const isRating = view.measure === 'rating';
    subjectLine.textContent = isRating ? 'Average star rating per month (months with at least 5 reviews in that channel).' : 'Written Amazon reviews per month.';
    legend.innerHTML = `
      <span class="legend-swatch"><span class="legend-dot" style="background:var(--graphite)"></span>New units (${intFmt(totals.new)})</span>
      <span class="legend-swatch"><span class="legend-dot" style="background:var(--steel)"></span>Refurbished (${intFmt(totals.renewed)})</span>
    `;
    const refurbShare = totals.total > 0 ? totals.renewed / totals.total : 0;
    if (totals.renewed > 0 && refurbShare < 0.02) {
      refurbNote.hidden = false;
      refurbNote.textContent = `Refurbished reviews are too few to see at this scale (${intFmt(totals.renewed)} in this window).`;
    } else {
      refurbNote.hidden = true;
    }
  }

  function redrawCharts() {
    const channels = { new: view.channels.new, renewed: view.channels.renewed };
    const isRating = view.measure === 'rating';
    const totals = windowTotals(detail.months, view.from, view.to);
    updateLegend(channels, totals);
    chartTitle.textContent = isRating
      ? computeRatingTakeaway(detail, view.from, view.to)
      : computeVolumeTakeaway(detail.months, view.from, view.to, channels);

    mainChartHolder.innerHTML = '';
    if (isRating) {
      mainChartHolder.appendChild(renderRatingMainChart({
        months: ratingMonths(detail.months), from: view.from, to: view.to, channels,
        completeThrough: portfolio.complete_through, events: [], width: 980, height: 300,
      }));
    } else {
      mainChartHolder.appendChild(renderVolumeChart({
        months: detail.months, from: view.from, to: view.to, channels,
        completeThrough: portfolio.complete_through, events: [], width: 980, height: 300,
      }));
    }

    rrTitle.textContent = isRating ? 'Monthly review volume' : 'Monthly average rating';
    rrNote.hidden = isRating;
    secondaryChartHolder.innerHTML = '';
    if (isRating) {
      secondaryChartHolder.appendChild(renderVolumeStrip({
        months: detail.months, from: view.from, to: view.to, channels, width: 980, height: 90,
      }));
    } else {
      secondaryChartHolder.appendChild(renderRatingStrip({
        months: detail.months, from: view.from, to: view.to,
        series: channels.new ? 'rating_new' : 'rating_renewed', width: 980, height: 100,
      }));
    }
  }

  function syncControlsFromView() {
    chNew.checked = view.channels.new;
    chRef.checked = view.channels.renewed;
    fromSel.value = view.from;
    toSel.value = view.to;
    const isRating = view.measure === 'rating';
    measureSwitch.setAttribute('aria-checked', String(!isRating));
    ratLabel.classList.toggle('switch-label-on', isRating);
    ratLabel.classList.toggle('switch-label-off', !isRating);
    volLabel.classList.toggle('switch-label-on', !isRating);
    volLabel.classList.toggle('switch-label-off', isRating);
    redrawCharts();
  }

  chNew.addEventListener('change', () => {
    if (!chNew.checked && !chRef.checked) { chNew.checked = true; hint.hidden = false; setTimeout(() => { hint.hidden = true; }, 3000); }
    setView({ channels: { new: chNew.checked } });
  });
  chRef.addEventListener('change', () => {
    if (!chNew.checked && !chRef.checked) { chRef.checked = true; hint.hidden = false; setTimeout(() => { hint.hidden = true; }, 3000); }
    setView({ channels: { renewed: chRef.checked } });
  });
  fromSel.addEventListener('change', () => {
    let f = fromSel.value;
    if (monthIndex(f) > monthIndex(toSel.value)) toSel.value = f;
    setView({ from: f, to: toSel.value });
  });
  toSel.addEventListener('change', () => {
    let t = toSel.value;
    if (monthIndex(t) < monthIndex(fromSel.value)) fromSel.value = t;
    setView({ from: fromSel.value, to: t });
  });
  measureSwitch.addEventListener('click', () => {
    setView({ measure: view.measure === 'rating' ? 'volume' : 'rating' });
  });

  const unsubscribe = onViewChanged((e) => {
    if (e.detail.productId !== id) return;
    syncControlsFromView();
  });
  syncControlsFromView();

  // ---- right rail: "What owners report" ----
  const rail = document.createElement('aside');
  rail.className = 'product-rail';
  layout.appendChild(rail);

  if (!detail.themes && !detail.lifecycle) {
    const h2 = document.createElement('h2');
    h2.textContent = 'What owners report';
    rail.appendChild(h2);
    const note = document.createElement('p');
    note.className = 'rail-intro';
    note.textContent = 'Complaint analysis covers units only; this listing has too few new-unit reviews for a breakdown.';
    rail.appendChild(note);
  } else {
    renderComplaintMix(rail, product, detail, labels);
    // The longer tables and charts sit under the timeline, where the main column has room for them.
    const below = document.createElement('div');
    below.className = 'product-below';
    main.appendChild(below);
    renderYearTable(below, detail, labels);
    renderLifecycle(below, detail);
    renderRefurb(below, detail, portfolio);
  }

  const disclosure = document.createElement('details');
  disclosure.className = 'listings-disclosure';
  const summary = document.createElement('summary');
  summary.textContent = `Listings (${detail.listings.length})`;
  disclosure.appendChild(summary);
  const table = document.createElement('table');
  table.className = 'listings-table';
  table.innerHTML = `
    <thead><tr><th>ASIN</th><th>Segment</th><th>Link method</th><th>Rating</th></tr></thead>
    <tbody>${detail.listings.map((l) => `<tr><td>${l.asin}</td><td>${l.segment.replace('_', ' ')}</td><td>${l.method.replace('_', ' ')}</td><td class="mono">${l.rating !== null ? decFmt(l.rating, 1) : EMPTY}</td></tr>`).join('')}</tbody>
  `;
  disclosure.appendChild(table);
  rail.appendChild(disclosure);

  return unsubscribe;
}
