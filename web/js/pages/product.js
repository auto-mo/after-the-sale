import { loadProductDetail, loadPortfolio } from '../data.js?v=202609232353';
import { renderVolumeChart, renderRatingStrip, renderRatingMainChart, renderVolumeStrip, monthsInRange } from '../charts.js?v=202609232353';
import { intFmt, decFmt, pctFmt, rangeFmt, monthShort, monthLong, dateShort, monthIndex, humanizeLaunchSource, humanizeType, EMPTY } from '../format.js?v=202609232353';
import { view, setView, onViewChanged } from '../state.js?v=202609232353';
import { navigate } from '../router.js?v=202609232353';

const EVENT_TYPE_LABEL = {
  sibling_launch: 'Sibling launch',
  refurbished: 'Refurbished units appear',
  low_rating: 'Low-rating month',
};

function verdictTag({ verdict, effectPct }, { large = false } = {}) {
  const wrap = document.createElement('span');
  wrap.className = `verdict-tag${verdict === 'not_enough_data' ? ' verdict-not-enough' : ''}${large ? ' verdict-lg' : ''}`;
  const punch = document.createElement('span');
  punch.className = 'verdict-punch';
  const label = document.createElement('span');
  label.className = 'verdict-label';
  if (verdict === 'moved') {
    label.textContent = effectPct !== null && effectPct !== undefined && effectPct < 0 ? 'Moved down' : 'Moved up';
  } else if (verdict === 'no_clear_change') {
    label.textContent = 'No clear change';
  } else {
    label.textContent = 'Not enough data';
  }
  wrap.appendChild(punch);
  wrap.appendChild(label);
  return wrap;
}

function eventDetailLine(ev) {
  return `${ev.detail} · ${monthShort(ev.month)}`;
}

function buildMeta(product, detail) {
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

function computeRatingTakeaway(months, from, to, channels) {
  const data = monthsInRange(months, from, to);
  const series = channels.new ? 'rating_new' : 'rating_renewed';
  const pts = data.filter((r) => r[series] !== null && r[series] !== undefined).map((r) => ({ v: r[series], m: r.m }));
  if (!pts.length) return 'No rating data in the selected window';
  const min = pts.reduce((a, b) => (b.v < a.v ? b : a));
  const max = pts.reduce((a, b) => (b.v > a.v ? b : a));
  if (min.m === max.m) return `Average rating was ${decFmt(min.v, 2)} in ${monthLong(min.m)}`;
  return `Rating peaked at ${decFmt(max.v, 2)} in ${monthLong(max.m)}, lowest was ${decFmt(min.v, 2)} in ${monthLong(min.m)}`;
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
  meta.innerHTML = buildMeta(product, detail).map((b) => `<span>${b}</span>`).join('');
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
  // Default "To" is the last fully-collected month, not the trailing partial
  // months the data still carries (down to 418 reviews in August 2023).
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
    <span id="measure-vol-label" class="switch-label-on">Volume</span>
    <button type="button" id="measure-switch" class="switch" role="switch" aria-checked="false" aria-labelledby="measure-vol-label measure-rat-label"></button>
    <span id="measure-rat-label">Rating</span>
  `;
  switchGroup.querySelector('.switch').innerHTML =
    '<span class="switch-knob"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M7 7h11l-3-3M17 17H6l3 3"/></svg></span>';
  controls.appendChild(switchGroup);
  const measureSwitch = switchGroup.querySelector('#measure-switch');
  const volLabel = switchGroup.querySelector('#measure-vol-label');
  const ratLabel = switchGroup.querySelector('#measure-rat-label');

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

  function eventMarkersFor(chartFrom, chartTo) {
    return detail.events
      .filter((e) => monthIndex(e.month) >= monthIndex(chartFrom) && monthIndex(e.month) <= monthIndex(chartTo))
      // Only tested events are marked, matching the rail; untested ones would crowd the chart without adding insight.
      .filter((e) => e.verdict !== 'not_enough_data')
      .map((e) => ({ month: e.month, type: e.type, detail: e.detail }));
  }

  function updateLegend(channels, totals) {
    const isRating = view.measure === 'rating';
    subjectLine.textContent = isRating ? 'Average star rating per month.' : 'Written Amazon reviews per month.';
    legend.innerHTML = `
      <span class="legend-swatch"><span class="legend-dot" style="background:var(--graphite)"></span>New units (${intFmt(totals.new)})</span>
      <span class="legend-swatch"><span class="legend-dot" style="background:var(--steel)"></span>Refurbished (${intFmt(totals.renewed)})</span>
      <span class="legend-swatch"><span class="legend-dash"></span>Event</span>
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
      ? computeRatingTakeaway(detail.months, view.from, view.to, channels)
      : computeVolumeTakeaway(detail.months, view.from, view.to, channels);

    mainChartHolder.innerHTML = '';
    const events = eventMarkersFor(view.from, view.to);
    if (isRating) {
      mainChartHolder.appendChild(renderRatingMainChart({
        months: detail.months, from: view.from, to: view.to, channels,
        completeThrough: portfolio.complete_through, events, width: 980, height: 300,
      }));
    } else {
      mainChartHolder.appendChild(renderVolumeChart({
        months: detail.months, from: view.from, to: view.to, channels,
        completeThrough: portfolio.complete_through, events, width: 980, height: 300,
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
    measureSwitch.setAttribute('aria-checked', String(isRating));
    volLabel.classList.toggle('switch-label-on', !isRating);
    volLabel.classList.toggle('switch-label-off', isRating);
    ratLabel.classList.toggle('switch-label-on', isRating);
    ratLabel.classList.toggle('switch-label-off', !isRating);
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

  // ---- right rail ----
  const rail = document.createElement('aside');
  rail.className = 'product-rail';
  layout.appendChild(rail);

  const railTitle = document.createElement('h2');
  railTitle.textContent = `What moved ${product.model || product.id}`;
  rail.appendChild(railTitle);
  const railIntro = document.createElement('p');
  railIntro.className = 'rail-intro';
  railIntro.textContent = 'Events detected on this product, each tested against similar products that had no such event.';
  rail.appendChild(railIntro);

  if (!detail.events.length) {
    const none = document.createElement('p');
    none.className = 'rail-intro';
    none.textContent = 'No events were detected for this product.';
    rail.appendChild(none);
  }

  // Tested events first (moved, then no clear change), each group in date order; untested ones go in a
  // collapsed group underneath, since they carry no insight on their own.
  const RANK = { moved: 0, no_clear_change: 1, not_enough_data: 2 };
  const ordered = [...detail.events].sort((a, b) => (RANK[a.verdict] ?? 3) - (RANK[b.verdict] ?? 3) || String(a.month).localeCompare(String(b.month)));
  const tested = ordered.filter((e) => e.verdict !== 'not_enough_data');
  const untested = ordered.filter((e) => e.verdict === 'not_enough_data');
  if (detail.events.length && !tested.length) {
    const noneTested = document.createElement('p');
    noneTested.className = 'rail-intro';
    noneTested.textContent = 'None of this product\'s events had enough data to test.';
    rail.appendChild(noneTested);
  }
  let target = rail;
  const renderEvent = (ev) => {
    const item = document.createElement('div');
    item.className = 'event-item';
    const head = document.createElement('div');
    head.className = 'event-head';
    const t = document.createElement('span');
    t.className = 'event-title';
    t.textContent = EVENT_TYPE_LABEL[ev.type] || ev.type;
    head.appendChild(t);
    head.appendChild(verdictTag({ verdict: ev.verdict, effectPct: ev.effect_pct }));
    item.appendChild(head);

    const sub = document.createElement('span');
    sub.className = 'event-sub';
    sub.textContent = eventDetailLine(ev);
    item.appendChild(sub);

    const changeRow = document.createElement('div');
    changeRow.className = 'event-change-row';
    const changeLabel = document.createElement('span');
    changeLabel.textContent = 'Change vs comparison';
    const changeVal = document.createElement('span');
    changeVal.className = 'mono';
    changeVal.textContent = ev.effect_pct !== null && ev.effect_pct !== undefined ? pctFmt(ev.effect_pct) : EMPTY;
    changeRow.appendChild(changeLabel);
    changeRow.appendChild(changeVal);
    item.appendChild(changeRow);
    if (ev.effect_pct !== null && ev.effect_pct !== undefined) {
      const rangeLine = document.createElement('div');
      rangeLine.className = 'event-change-range mono';
      rangeLine.textContent = rangeFmt(ev.lo_pct, ev.hi_pct);
      item.appendChild(rangeLine);
    }

    if (ev.reason) {
      const reason = document.createElement('span');
      reason.className = 'event-reason';
      reason.textContent = ev.reason;
      item.appendChild(reason);
    }

    const link = document.createElement('a');
    link.className = 'event-link';
    link.href = `#/event/${product.id}/${ev.id}`;
    link.textContent = 'Open the evidence';
    item.appendChild(link);

    target.appendChild(item);
  };
  tested.forEach(renderEvent);
  if (untested.length) {
    const group = document.createElement('details');
    group.className = 'untested-group';
    const sum = document.createElement('summary');
    sum.textContent = `${untested.length} event${untested.length === 1 ? '' : 's'} without enough data to test`;
    group.appendChild(sum);
    rail.appendChild(group);
    target = group;
    untested.forEach(renderEvent);
    target = rail;
  }

  const notTestable = document.createElement('div');
  notTestable.className = 'not-testable';
  notTestable.innerHTML = `
    <span class="not-testable-title">Not testable with free data</span>
    <span class="honest-note">Price changes, stock-outs, sales rank and buy box need price and seller history.</span>
  `;
  rail.appendChild(notTestable);

  const honest = document.createElement('p');
  honest.className = 'honest-note';
  honest.textContent = `Across all ${intFmt(portfolio.stats.events_tested)} testable events, none shows a change beyond what chance produces. See Findings for the averages that do hold.`;
  rail.appendChild(honest);

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
