import { loadProductDetail } from '../data.js?v=202609232243';
import { renderEventStudyChart } from '../charts.js?v=202609232243';
import { decFmt, pctFmt, rangeFmt, monthShort, addMonths, EMPTY } from '../format.js?v=202609232243';
import { navigate } from '../router.js?v=202609232243';

const EVENT_TYPE_LABEL = {
  sibling_launch: 'Sibling launch',
  refurbished: 'Refurbished units appear',
  low_rating: 'Low-rating month',
};

function verdictTag(ev) {
  const wrap = document.createElement('span');
  wrap.className = `verdict-tag verdict-lg${ev.verdict === 'not_enough_data' ? ' verdict-not-enough' : ''}`;
  const punch = document.createElement('span');
  punch.className = 'verdict-punch';
  const label = document.createElement('span');
  label.className = 'verdict-label';
  if (ev.verdict === 'moved') label.textContent = ev.effect_pct < 0 ? 'Moved down' : 'Moved up';
  else if (ev.verdict === 'no_clear_change') label.textContent = 'No clear change';
  else label.textContent = 'Not enough data';
  wrap.appendChild(punch);
  wrap.appendChild(label);
  return wrap;
}

// Model codes (AF150, NV360...) keep their case everywhere; only the verdict
// decides which sentence shape is used, so the headline never contradicts
// the tag next to it.
function headline(ev, product) {
  const name = product.model || product.id;
  if (ev.verdict === 'moved') {
    const dir = ev.effect_pct < 0 ? 'down' : 'up';
    return { title: `${name}'s new-unit reviews moved ${dir} ${decFmt(Math.abs(ev.effect_pct), 1)}% versus comparison after ${ev.detail}.`, sub: null };
  }
  if (ev.verdict === 'no_clear_change') {
    return {
      title: `No clear change in ${name}'s new-unit reviews after ${ev.detail}.`,
      sub: `Change versus comparison ${pctFmt(ev.effect_pct)}, within the product's normal swings (range ${rangeFmt(ev.lo_pct, ev.hi_pct)}).`,
    };
  }
  return {
    title: `Not enough data to test ${name} around ${ev.detail}.`,
    sub: ev.reason ? `${ev.reason.charAt(0).toUpperCase()}${ev.reason.slice(1)}.` : null,
  };
}

export async function render(container, params) {
  const { productId, eventId } = params;
  container.innerHTML = '<div class="empty-state">Loading evidence…</div>';

  let result;
  try {
    result = await loadProductDetail(productId);
  } catch (err) {
    container.innerHTML = `<div class="error-state">Could not load this product's data. ${err.message}</div>`;
    return;
  }
  if (result.notFound || !result.product || !result.detail) {
    container.innerHTML = '<div class="error-state">This product or its events could not be found.</div>';
    return;
  }
  const { product, detail } = result;
  const events = detail.events;
  const ev = events.find((e) => e.id === eventId);
  if (!ev) {
    container.innerHTML = '<div class="error-state">This event could not be found for this product.</div>';
    return;
  }

  container.innerHTML = '';
  const layout = document.createElement('div');
  layout.className = 'event-layout';
  container.appendChild(layout);

  // ---- setup panel ----
  const setup = document.createElement('form');
  setup.className = 'event-setup';
  setup.setAttribute('aria-label', 'Question setup');
  setup.addEventListener('submit', (e) => e.preventDefault());
  layout.appendChild(setup);

  const setupTitle = document.createElement('h2');
  setupTitle.textContent = 'Set up the question';
  setup.appendChild(setupTitle);

  const types = [...new Set(events.map((e) => e.type))];
  const typeGroup = document.createElement('div');
  typeGroup.className = 'field-group';
  typeGroup.innerHTML = `<label for="et-sel">Event type</label>
    <select id="et-sel">${types.map((t) => `<option value="${t}"${t === ev.type ? ' selected' : ''}>${EVENT_TYPE_LABEL[t] || t}</option>`).join('')}</select>`;
  setup.appendChild(typeGroup);
  const typeSel = typeGroup.querySelector('#et-sel');

  const eventGroup = document.createElement('div');
  eventGroup.className = 'field-group';
  eventGroup.innerHTML = `<label for="ev-sel">Event</label><select id="ev-sel"></select>`;
  setup.appendChild(eventGroup);
  const eventSel = eventGroup.querySelector('#ev-sel');

  function fillEventSelect() {
    const filtered = events.filter((e) => e.type === typeSel.value);
    eventSel.innerHTML = filtered.map((e) => `<option value="${e.id}"${e.id === ev.id ? ' selected' : ''}>${e.detail} · ${monthShort(e.month)}</option>`).join('');
  }
  fillEventSelect();
  typeSel.addEventListener('change', () => {
    fillEventSelect();
    navigate(`/event/${productId}/${eventSel.value}`);
  });
  eventSel.addEventListener('change', () => navigate(`/event/${productId}/${eventSel.value}`));

  const windowGroup = document.createElement('div');
  windowGroup.className = 'field-group';
  windowGroup.innerHTML = `<label>Window around the event</label><span class="field-note">${ev.window} months before and after</span>`;
  setup.appendChild(windowGroup);

  const cmpGroup = document.createElement('div');
  cmpGroup.className = 'field-group';
  const controlsNote = ev.n_controls < 3
    ? 'Fewer than 3 comparable products. The comparison could not be run.'
    : `Matched on product type, age and prior volume: ${ev.n_controls} comparison products (${ev.control_tier}).`;
  cmpGroup.innerHTML = `<label>Compared against</label><span class="field-note">${controlsNote}</span>`;
  setup.appendChild(cmpGroup);

  // ---- main evidence ----
  const main = document.createElement('section');
  main.className = 'event-main';
  layout.appendChild(main);

  const breadcrumb = document.createElement('nav');
  breadcrumb.className = 'breadcrumb';
  breadcrumb.setAttribute('aria-label', 'Breadcrumb');
  breadcrumb.innerHTML = `<a href="#/product/${product.id}">${product.model || product.id}</a> / ${(EVENT_TYPE_LABEL[ev.type] || ev.type).toLowerCase()} / ${ev.related || monthShort(ev.month)}`;
  main.appendChild(breadcrumb);

  const { title: headlineText, sub: headlineSub } = headline(ev, product);
  const headRow = document.createElement('div');
  headRow.className = 'event-headline-row';
  const h1 = document.createElement('h1');
  h1.textContent = headlineText;
  headRow.appendChild(h1);
  headRow.appendChild(verdictTag(ev));
  main.appendChild(headRow);
  if (headlineSub) {
    const subP = document.createElement('p');
    subP.className = 'field-note';
    subP.style.marginTop = '-8px';
    subP.textContent = headlineSub;
    main.appendChild(subP);
  }

  const chartCard = document.createElement('div');
  chartCard.className = 'card';
  const chartHead = document.createElement('div');
  chartHead.style.display = 'flex';
  chartHead.style.justifyContent = 'space-between';
  chartHead.style.margin = '0 12px';
  chartHead.style.flexWrap = 'wrap';
  chartHead.style.gap = '8px';
  const chartH2 = document.createElement('h2');
  chartH2.style.fontSize = '16px';
  chartH2.textContent = `${product.model || product.id} new-unit reviews, months relative to the event`;
  chartHead.appendChild(chartH2);
  const chartLegend = document.createElement('div');
  chartLegend.className = 'legend-row';
  chartLegend.style.margin = '0';
  chartLegend.innerHTML = `
    <span class="legend-swatch"><span class="legend-dot" style="background:var(--graphite)"></span>${product.model || product.id} (actual)</span>
    ${ev.band ? '<span class="legend-swatch"><span class="legend-dot" style="background:var(--steel);opacity:.4"></span>comparison band</span>' : ''}
  `;
  chartHead.appendChild(chartLegend);
  chartCard.appendChild(chartHead);

  const actualByOffset = new Map();
  const byMonth = new Map(detail.months.map((m) => [m.m, m]));
  for (let r = -ev.window; r <= ev.window; r += 1) {
    const m = addMonths(ev.month, r);
    const row = byMonth.get(m);
    if (row) actualByOffset.set(r, row.new || 0);
  }
  chartCard.appendChild(renderEventStudyChart({
    eventMonth: ev.month,
    band: ev.band || null,
    actualByOffset,
    windowSize: ev.window,
    eventLabel: `${ev.detail} · ${monthShort(ev.month)}`,
  }));
  if (!ev.band) {
    const note = document.createElement('p');
    note.className = 'field-note';
    note.style.margin = '4px 12px 0';
    note.textContent = 'No comparison band is available for this event; the bars show this product’s own reviews only.';
    chartCard.appendChild(note);
  }
  main.appendChild(chartCard);

  const hasEffect = ev.effect_pct !== null && ev.effect_pct !== undefined;
  const hasMeans = ev.pre_mean !== null && ev.pre_mean !== undefined && ev.post_mean !== null && ev.post_mean !== undefined;
  const statGrid = document.createElement('div');
  statGrid.className = 'stat-grid';
  statGrid.innerHTML = `
    <div class="stat-tile">
      <span class="stat-label">Before, raw monthly average</span>
      <span class="stat-value mono">${hasMeans ? decFmt(ev.pre_mean, 1) : EMPTY}</span>
      <span class="stat-note">months −${ev.window} to −1, unadjusted</span>
    </div>
    <div class="stat-tile">
      <span class="stat-label">After, raw monthly average</span>
      <span class="stat-value mono">${hasMeans ? decFmt(ev.post_mean, 1) : EMPTY}</span>
      <span class="stat-note">months +1 to +${ev.window}, unadjusted</span>
    </div>
    <div class="stat-tile stat-highlight">
      <span class="stat-label">Change vs comparison</span>
      <span class="stat-value mono">${hasEffect ? pctFmt(ev.effect_pct) : EMPTY}</span>
      <span class="stat-note">${hasEffect ? `${rangeFmt(ev.lo_pct, ev.hi_pct)} · the number the verdict rests on` : (ev.reason || 'not computed')}</span>
    </div>
  `;
  main.appendChild(statGrid);

  if (hasEffect && hasMeans) {
    const rawFell = ev.post_mean < ev.pre_mean;
    const rawRose = ev.post_mean > ev.pre_mean;
    const mismatch = (rawFell && ev.effect_pct > 0) || (rawRose && ev.effect_pct < 0);
    if (mismatch) {
      const note = document.createElement('p');
      note.className = 'field-note';
      note.textContent = rawFell
        ? `Both fell; ${product.model || product.id} fell less than the comparison group.`
        : `Both rose; ${product.model || product.id} rose less than the comparison group.`;
      main.appendChild(note);
    }
  }

  const cautions = [];
  if (ev.control_tier && ev.control_tier !== 'strict') {
    cautions.push(`Compared with a looser set of products (${ev.control_tier}), because there were too few close matches.`);
  }
  if (ev.near_zero_after) {
    cautions.push('Reviews fell to near zero after this event; that can reflect a planned discontinuation rather than a reaction to the event.');
  }
  if (ev.verdict === 'not_enough_data' && ev.reason) {
    cautions.push(`Not enough data: ${ev.reason}.`);
  }
  if (ev.n_controls > 0 && ev.n_controls < 5 && ev.verdict !== 'not_enough_data') {
    cautions.push(`Only ${ev.n_controls} comparison products were available, so the range is wide.`);
  }
  if (cautions.length) {
    const cautionCard = document.createElement('div');
    cautionCard.className = 'card';
    const h = document.createElement('h2');
    h.style.fontSize = '15px';
    h.style.marginBottom = '8px';
    h.textContent = 'Cautions';
    cautionCard.appendChild(h);
    const ul = document.createElement('ul');
    ul.className = 'caution-list';
    ul.innerHTML = cautions.map((c) => `<li>${c}</li>`).join('');
    cautionCard.appendChild(ul);
    main.appendChild(cautionCard);
  }

  const backLink = document.createElement('a');
  backLink.href = `#/product/${product.id}`;
  backLink.textContent = `Back to ${product.model || product.id}`;
  main.appendChild(backLink);
}
