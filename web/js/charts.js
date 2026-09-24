// Inline SVG chart builders. No chart library, per spec. Charts are built as
// real DOM (createElementNS) so hover/focus tooltips and keyboard access work.
// Every chart is fluid: it declares a reference viewBox and scales uniformly
// to its card's width via CSS (width:100%, height:auto) so nothing ever
// forces a horizontal scrollbar and text is never stretched out of shape.

import { monthShort, monthLong, monthIndex, intFmt, decFmt } from './format.js?v=202609241634';

const SVG_NS = 'http://www.w3.org/2000/svg';
const MINUS = '−';

/** Read a color token's current value (light or dark theme) at draw time,
 * so charts never hardcode a hex that would go wrong under `data-theme`. */
export function cssVar(name) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || '#000';
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined) continue;
    node.setAttribute(k, v);
  }
  for (const child of children) node.appendChild(child);
  return node;
}

function makeSvg(totalW, height, ariaLabel) {
  return el('svg', {
    viewBox: `0 0 ${totalW} ${height}`,
    role: 'img',
    'aria-label': ariaLabel,
    style: `display:block;width:100%;height:auto;max-width:100%`,
  });
}

/** Slice a months array to an inclusive [from, to] range, filling any gap
 * months with zeros so the x-axis stays evenly spaced. */
export function monthsInRange(months, from, to) {
  const byMonth = new Map(months.map((row) => [row.m, row]));
  const fromIdx = monthIndex(from);
  const toIdx = monthIndex(to);
  const out = [];
  for (let idx = fromIdx; idx <= toIdx; idx += 1) {
    const y = Math.floor(idx / 12);
    const mo = (idx % 12) + 1;
    const m = `${y}-${String(mo).padStart(2, '0')}`;
    out.push(byMonth.get(m) || { m, new: 0, renewed: 0, rating_new: null, rating_renewed: null });
  }
  return out;
}

function niceStep(maxVal, divisions = 4) {
  if (maxVal <= 0) return { step: 1, niceMax: 4 };
  const rough = maxVal / divisions;
  const mag = 10 ** Math.floor(Math.log10(rough));
  const candidates = [1, 2, 2.5, 5, 10];
  let step = mag * 10;
  for (const c of candidates) {
    if (rough <= c * mag) { step = c * mag; break; }
  }
  const niceMax = Math.ceil(maxVal / step) * step;
  return { step, niceMax: niceMax === 0 ? step : niceMax };
}

/** Choose a year interval (1/2/5/10/20/50) so year-tick labels have room to
 * breathe at the chart's reference width. */
function yearTickStep(firstYear, lastYear, plotW, minPxPerTick = 42) {
  const span = Math.max(1, lastYear - firstYear);
  const candidates = [1, 2, 5, 10, 20, 50];
  for (const c of candidates) {
    const ticks = Math.floor(span / c) + 1;
    if (plotW / ticks >= minPxPerTick) return c;
  }
  return candidates[candidates.length - 1];
}

function shortEventLabel(ev) {
  if (ev.type === 'refurbished') return 'Refurbished units';
  if (ev.type === 'low_rating') return 'Low rating';
  if (ev.type === 'sibling_launch') {
    const code = (ev.detail || '').split(' ')[0];
    return code ? `${code} launched` : 'Sibling launch';
  }
  return ev.detail || '';
}

/** Assign each event marker a row (0-2) and an x-start so labels stack
 * instead of overlapping, flipping to the left of their line when they
 * would run past the right edge of the plot. */
function layoutEventLabels(sortedEvents, findIndex, padL, plotW, bw) {
  const rows = [[], [], []];
  const placed = [];
  for (const ev of sortedEvents) {
    const idx = findIndex(ev.month);
    if (idx === -1) continue;
    const x = padL + idx * bw + bw / 2;
    const text = shortEventLabel(ev);
    const labelW = Math.min(Math.max(50, text.length * 6.4 + 14), 170);
    let start = x;
    if (start + labelW > padL + plotW) start = x - labelW - 4;
    if (start < padL) start = padL;
    const end = start + labelW;
    let row = 2;
    for (let r = 0; r < 3; r += 1) {
      const overlap = rows[r].some((iv) => !(end + 4 < iv.start || start - 4 > iv.end));
      if (!overlap) { row = r; break; }
    }
    rows[row].push({ start, end });
    placed.push({ x, start, labelW, row, text });
  }
  return placed;
}

function buildTooltip(container) {
  const tip = document.createElement('div');
  tip.setAttribute('role', 'status');
  tip.style.position = 'absolute';
  tip.style.pointerEvents = 'none';
  tip.style.background = '#16191D';
  tip.style.color = '#fff';
  tip.style.font = '12px "IBM Plex Sans", sans-serif';
  tip.style.padding = '6px 9px';
  tip.style.borderRadius = '3px';
  tip.style.lineHeight = '1.4';
  tip.style.whiteSpace = 'nowrap';
  tip.style.zIndex = '5';
  tip.style.display = 'none';
  container.style.position = 'relative';
  container.appendChild(tip);
  return tip;
}

function showTooltip(tip, container, x, y, lines) {
  tip.innerHTML = '';
  for (const line of lines) {
    const d = document.createElement('div');
    d.textContent = line;
    tip.appendChild(d);
  }
  tip.style.display = 'block';
  const contRect = container.getBoundingClientRect();
  let left = x + 12;
  if (left + 180 > contRect.width) left = x - 12 - 180;
  tip.style.left = `${Math.max(0, left)}px`;
  tip.style.top = `${Math.max(0, y - 10)}px`;
}

function hideTooltip(tip) {
  tip.style.display = 'none';
}

/**
 * Monthly stacked-bar volume chart: new units (graphite) + refurbished
 * (steel), incomplete-data hatch after completeThrough, orange dashed event
 * markers, hover/focus tooltip. Returns a wrapper <div> to append.
 */
export function renderVolumeChart({
  months, from, to, channels = { new: true, renewed: true }, completeThrough,
  events = [], width = 980, height = 300, ariaLabel = 'Reviews per month',
}) {
  const wrap = document.createElement('div');
  const data = monthsInRange(months, from, to);
  const n = data.length;
  const padL = 44;
  const padR = 16;
  const padBottom = 28;
  const plotW = width - padL - padR;
  const bw = plotW / n;

  const sortedEvents = [...events].sort((a, b) => monthIndex(a.month) - monthIndex(b.month));
  const findIndex = (m) => data.findIndex((r) => r.m === m);
  const placedLabels = layoutEventLabels(sortedEvents, findIndex, padL, plotW, bw);
  const rowsUsed = placedLabels.length ? Math.max(...placedLabels.map((p) => p.row)) + 1 : 0;
  const padTop = rowsUsed ? 20 + rowsUsed * 20 : 20;
  const plotH = height - padTop - padBottom;
  const totalW = plotW + padL + padR;

  const values = data.map((r) => (channels.new ? r.new || 0 : 0) + (channels.renewed ? r.renewed || 0 : 0));
  const maxVal = Math.max(1, ...values);
  const { step, niceMax } = niceStep(maxVal);
  const yScale = (v) => padTop + plotH - (v / niceMax) * plotH;

  const svg = makeSvg(totalW, height, ariaLabel);

  // gridlines + y labels
  for (let v = 0; v <= niceMax + 0.0001; v += step) {
    const y = yScale(v);
    svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: y, y2: y, stroke: cssVar('--hairline'), 'stroke-width': 1 }));
    svg.appendChild(el('text', { x: padL - 8, y: y + 4, 'text-anchor': 'end', 'font-family': 'IBM Plex Mono', 'font-size': 11, fill: cssVar('--muted') })).textContent = intFmt(v);
  }

  const barW = Math.max(1, bw * 0.72);

  // incomplete-data hatch
  if (completeThrough) {
    const completeIdx = monthIndex(completeThrough);
    const firstIncomplete = data.findIndex((r) => monthIndex(r.m) > completeIdx);
    if (firstIncomplete !== -1) {
      const hatchX = padL + firstIncomplete * bw;
      const defs = el('defs', {}, [
        el('pattern', { id: 'hatch', width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' }, [
          el('line', { x1: 0, y1: 0, x2: 0, y2: 6, stroke: cssVar('--hatch'), 'stroke-width': 2 }),
        ]),
      ]);
      svg.appendChild(defs);
      svg.appendChild(el('rect', { x: hatchX, y: padTop, width: padL + plotW - hatchX, height: plotH, fill: 'url(#hatch)' }));
      svg.appendChild(el('text', { x: padL + plotW - 4, y: padTop + 14, 'text-anchor': 'end', 'font-family': 'IBM Plex Sans', 'font-size': 11, fill: cssVar('--muted') })).textContent = 'incomplete data';
    }
  }

  // bars
  const barGroups = [];
  data.forEach((row, i) => {
    const x = padL + i * bw + (bw - barW) / 2;
    let yCursor = padTop + plotH;
    const g = el('g', {});
    if (channels.new) {
      const v = row.new || 0;
      const h = (v / niceMax) * plotH;
      g.appendChild(el('rect', { x, y: yCursor - h, width: barW, height: Math.max(h, v > 0 ? 0.6 : 0), fill: cssVar('--graphite') }));
      yCursor -= h;
    }
    if (channels.renewed) {
      const v = row.renewed || 0;
      const h = (v / niceMax) * plotH;
      g.appendChild(el('rect', { x, y: yCursor - h, width: barW, height: Math.max(h, v > 0 ? 0.6 : 0), fill: cssVar('--steel') }));
      yCursor -= h;
    }
    // full-height invisible hit target for hover/focus
    const hit = el('rect', {
      x: padL + i * bw, y: padTop, width: bw, height: plotH, fill: 'transparent', tabindex: '0',
      role: 'img', 'aria-label': `${monthLong(row.m)}: ${intFmt((row.new || 0) + (row.renewed || 0))} reviews`,
    });
    g.appendChild(hit);
    barGroups.push({ hit, row, x: padL + i * bw + bw / 2 });
    svg.appendChild(g);
  });

  // x axis with a collision-aware year interval
  svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: padTop + plotH, y2: padTop + plotH, stroke: cssVar('--ink'), 'stroke-width': 1 }));
  const firstYear = Number(data[0].m.slice(0, 4));
  const lastYear = Number(data[n - 1].m.slice(0, 4));
  const yStep = yearTickStep(firstYear, lastYear, plotW);
  let lastYear_ = null;
  let lastTickX = null;
  data.forEach((row, i) => {
    const y = Number(row.m.slice(0, 4));
    const mo = row.m.slice(5, 7);
    const x = padL + i * bw;
    // skip a label that would collide with the previous one (e.g. a mid-year start followed by January)
    if ((mo === '01' || i === 0) && y !== lastYear_ && (y - firstYear) % yStep === 0 && (lastTickX === null || x - lastTickX >= 40)) {
      lastTickX = x;
      svg.appendChild(el('line', { x1: x, x2: x, y1: padTop + plotH, y2: padTop + plotH + 5, stroke: cssVar('--ink') }));
      svg.appendChild(el('text', { x: x + 3, y: padTop + plotH + 18, 'font-family': 'IBM Plex Mono', 'font-size': 11, fill: cssVar('--muted') })).textContent = String(y);
      lastYear_ = y;
    }
  });

  // event markers: short labels, stacked rows, flipped left near the edge
  for (const p of placedLabels) {
    const labelY = padTop - 12 - p.row * 20;
    svg.appendChild(el('line', { x1: p.x, x2: p.x, y1: labelY + 8, y2: padTop + plotH, stroke: cssVar('--tag-orange'), 'stroke-width': 1.5, 'stroke-dasharray': '3 3' }));
    svg.appendChild(el('rect', { x: p.start, y: labelY - 9, width: p.labelW, height: 18, fill: '#fff', stroke: cssVar('--tag-orange') }));
    const t = el('text', { x: p.start + 6, y: labelY + 4, 'font-family': 'IBM Plex Sans', 'font-size': 11, fill: cssVar('--ink') });
    t.textContent = p.text;
    svg.appendChild(t);
  }

  wrap.appendChild(svg);
  const tip = buildTooltip(wrap);
  for (const { hit, row, x } of barGroups) {
    const lines = [monthLong(row.m)];
    if (channels.new) lines.push(`New: ${intFmt(row.new || 0)}`);
    if (channels.renewed) lines.push(`Refurbished: ${intFmt(row.renewed || 0)}`);
    if (row.rating_new !== null && row.rating_new !== undefined) lines.push(`Rating (new): ${decFmt(row.rating_new, 2)}`);
    const show = (clientY) => {
      const rect = wrap.getBoundingClientRect();
      const svgRect = svg.getBoundingClientRect();
      const scale = svgRect.width / totalW;
      showTooltip(tip, wrap, x * scale, (clientY ?? rect.top + 20) - rect.top, lines);
    };
    hit.addEventListener('mouseenter', (e) => show(e.clientY));
    hit.addEventListener('mousemove', (e) => show(e.clientY));
    hit.addEventListener('mouseleave', () => hideTooltip(tip));
    hit.addEventListener('focus', () => show(undefined));
    hit.addEventListener('blur', () => hideTooltip(tip));
  }

  return wrap;
}

/** Shared x-axis + event-marker + hatch drawing, used by both the volume and
 * rating main charts so they read as the same timeline. Returns padTop. */
function drawTimelineFrame(svg, { data, n, padL, plotW, bw, events, completeThrough, padTop, plotH }) {
  const plotBottomY = padTop + plotH;
  const sortedEvents = [...events].sort((a, b) => monthIndex(a.month) - monthIndex(b.month));
  const findIndex = (m) => data.findIndex((r) => r.m === m);
  const placedLabels = layoutEventLabels(sortedEvents, findIndex, padL, plotW, bw);

  // incomplete-data hatch, spanning the full plot height
  if (completeThrough) {
    const completeIdx = monthIndex(completeThrough);
    const firstIncomplete = data.findIndex((r) => monthIndex(r.m) > completeIdx);
    if (firstIncomplete !== -1) {
      const hatchX = padL + firstIncomplete * bw;
      const defs = el('defs', {}, [
        el('pattern', { id: 'hatch', width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' }, [
          el('line', { x1: 0, y1: 0, x2: 0, y2: 6, stroke: cssVar('--hatch'), 'stroke-width': 2 }),
        ]),
      ]);
      svg.appendChild(defs);
      svg.appendChild(el('rect', { x: hatchX, y: padTop, width: padL + plotW - hatchX, height: plotH, fill: 'url(#hatch)' }));
      svg.appendChild(el('text', { x: padL + plotW - 4, y: padTop + 14, 'text-anchor': 'end', 'font-family': 'IBM Plex Sans', 'font-size': 11, fill: cssVar('--muted') })).textContent = 'incomplete data';
    }
  }

  // x axis with a collision-aware year interval
  svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: plotBottomY, y2: plotBottomY, stroke: cssVar('--ink'), 'stroke-width': 1 }));
  const firstYear = Number(data[0].m.slice(0, 4));
  const yStep = yearTickStep(firstYear, Number(data[n - 1].m.slice(0, 4)), plotW);
  let lastYear_ = null;
  let lastTickX = null;
  data.forEach((row, i) => {
    const y = Number(row.m.slice(0, 4));
    const mo = row.m.slice(5, 7);
    const x = padL + i * bw;
    // skip a label that would collide with the previous one (e.g. a mid-year start followed by January)
    if ((mo === '01' || i === 0) && y !== lastYear_ && (y - firstYear) % yStep === 0 && (lastTickX === null || x - lastTickX >= 40)) {
      lastTickX = x;
      svg.appendChild(el('line', { x1: x, x2: x, y1: plotBottomY, y2: plotBottomY + 5, stroke: cssVar('--ink') }));
      svg.appendChild(el('text', { x: x + 3, y: plotBottomY + 18, 'font-family': 'IBM Plex Mono', 'font-size': 11, fill: cssVar('--muted') })).textContent = String(y);
      lastYear_ = y;
    }
  });

  // event markers: short labels, stacked rows, flipped left near the edge
  for (const p of placedLabels) {
    const labelY = padTop - 12 + p.row * 20;
    svg.appendChild(el('line', { x1: p.x, x2: p.x, y1: labelY + 8, y2: plotBottomY, stroke: cssVar('--tag-orange'), 'stroke-width': 1.5, 'stroke-dasharray': '3 3' }));
    svg.appendChild(el('rect', { x: p.start, y: labelY - 9, width: p.labelW, height: 18, fill: '#fff', stroke: cssVar('--tag-orange') }));
    const t = el('text', { x: p.start + 6, y: labelY + 4, 'font-family': 'IBM Plex Sans', 'font-size': 11, fill: cssVar('--ink') });
    t.textContent = p.text;
    svg.appendChild(t);
  }

  return placedLabels;
}

function rowsUsedFor(events, data, padL, plotW, bw) {
  const sortedEvents = [...events].sort((a, b) => monthIndex(a.month) - monthIndex(b.month));
  const findIndex = (m) => data.findIndex((r) => r.m === m);
  const placed = layoutEventLabels(sortedEvents, findIndex, padL, plotW, bw);
  return placed.length ? Math.max(...placed.map((p) => p.row)) + 1 : 0;
}

/**
 * Compact bars-only volume strip (used under the main chart when the
 * Volume/Rating switch is set to Rating, so the reader keeps the volume
 * context). No event labels or axis text: it reads alongside the main chart.
 */
export function renderVolumeStrip({ months, from, to, channels = { new: true, renewed: true }, width = 980, height = 90 }) {
  const wrap = document.createElement('div');
  const data = monthsInRange(months, from, to);
  const n = data.length;
  const padL = 44;
  const padR = 16;
  const padTop = 6;
  const padBottom = 6;
  const plotW = width - padL - padR;
  const plotH = height - padTop - padBottom;
  const totalW = plotW + padL + padR;
  const bw = plotW / n;

  const values = data.map((r) => (channels.new ? r.new || 0 : 0) + (channels.renewed ? r.renewed || 0 : 0));
  const maxVal = Math.max(1, ...values);
  const { niceMax } = niceStep(maxVal, 2);

  const svg = makeSvg(totalW, height, 'Reviews per month (volume context)');
  svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: padTop, y2: padTop, stroke: cssVar('--hairline') }));
  svg.appendChild(el('text', { x: padL - 8, y: padTop + 4, 'text-anchor': 'end', 'font-family': 'IBM Plex Mono', 'font-size': 11, fill: cssVar('--muted') })).textContent = intFmt(niceMax);
  svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: padTop + plotH, y2: padTop + plotH, stroke: cssVar('--ink') }));
  svg.appendChild(el('text', { x: padL - 8, y: padTop + plotH + 4, 'text-anchor': 'end', 'font-family': 'IBM Plex Mono', 'font-size': 11, fill: cssVar('--muted') })).textContent = '0';

  const barW = Math.max(1, bw * 0.72);
  const tip = buildTooltip(wrap);
  const hits = [];
  data.forEach((row, i) => {
    const x = padL + i * bw + (bw - barW) / 2;
    let yCursor = padTop + plotH;
    if (channels.new) {
      const v = row.new || 0;
      const h = (v / niceMax) * plotH;
      svg.appendChild(el('rect', { x, y: yCursor - h, width: barW, height: Math.max(h, v > 0 ? 0.5 : 0), fill: cssVar('--graphite') }));
      yCursor -= h;
    }
    if (channels.renewed) {
      const v = row.renewed || 0;
      const h = (v / niceMax) * plotH;
      svg.appendChild(el('rect', { x, y: yCursor - h, width: barW, height: Math.max(h, v > 0 ? 0.5 : 0), fill: cssVar('--steel') }));
    }
    const hit = el('rect', { x: padL + i * bw, y: padTop, width: bw, height: plotH, fill: 'transparent', tabindex: '0', role: 'img', 'aria-label': `${monthLong(row.m)}: ${intFmt((row.new || 0) + (row.renewed || 0))} reviews` });
    svg.appendChild(hit);
    hits.push({ hit, row, x: padL + i * bw + bw / 2 });
  });

  wrap.appendChild(svg);
  for (const { hit, row, x } of hits) {
    const lines = [monthLong(row.m)];
    if (channels.new) lines.push(`New: ${intFmt(row.new || 0)}`);
    if (channels.renewed) lines.push(`Refurbished: ${intFmt(row.renewed || 0)}`);
    const show = (clientY) => {
      const rect = wrap.getBoundingClientRect();
      const svgRect = svg.getBoundingClientRect();
      const scale = svgRect.width / totalW;
      showTooltip(tip, wrap, x * scale, (clientY ?? rect.top + 10) - rect.top, lines);
    };
    hit.addEventListener('mouseenter', (e) => show(e.clientY));
    hit.addEventListener('mousemove', (e) => show(e.clientY));
    hit.addEventListener('mouseleave', () => hideTooltip(tip));
    hit.addEventListener('focus', () => show(undefined));
    hit.addEventListener('blur', () => hideTooltip(tip));
  }
  return wrap;
}

/**
 * Main chart for the Rating measure: monthly average rating as lines (new
 * units graphite, refurbished steel when shown) with dots per month that has
 * data, same x axis / event markers / hatch as the volume chart.
 */
export function renderRatingMainChart({
  months, from, to, channels = { new: true, renewed: true }, completeThrough,
  events = [], width = 980, height = 300, ariaLabel = 'Average rating per month',
}) {
  const wrap = document.createElement('div');
  const data = monthsInRange(months, from, to);
  const n = data.length;
  const padL = 44;
  const padR = 16;
  const padBottom = 28;
  const plotW = width - padL - padR;
  const bw = plotW / n;

  const rowsUsed = rowsUsedFor(events, data, padL, plotW, bw);
  const padTop = rowsUsed ? 20 + rowsUsed * 20 : 20;
  const plotH = height - padTop - padBottom;
  const totalW = plotW + padL + padR;

  const seriesVals = [];
  if (channels.new) data.forEach((r) => { if (r.rating_new !== null && r.rating_new !== undefined) seriesVals.push(r.rating_new); });
  if (channels.renewed) data.forEach((r) => { if (r.rating_renewed !== null && r.rating_renewed !== undefined) seriesVals.push(r.rating_renewed); });
  const allAbove3 = seriesVals.length > 0 && seriesVals.every((v) => v > 3);
  const yMin = allAbove3 ? 3 : 1;
  const yMax = 5;
  const yStep = (yMax - yMin) <= 2 ? 0.5 : 1;
  const yScale = (v) => padTop + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

  const svg = makeSvg(totalW, height, ariaLabel);

  for (let v = yMin; v <= yMax + 0.0001; v += yStep) {
    const y = yScale(v);
    svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: y, y2: y, stroke: cssVar('--hairline'), 'stroke-width': 1 }));
    svg.appendChild(el('text', { x: padL - 8, y: y + 4, 'text-anchor': 'end', 'font-family': 'IBM Plex Mono', 'font-size': 11, fill: cssVar('--muted') })).textContent = decFmt(v, yStep < 1 ? 1 : 0);
  }

  drawTimelineFrame(svg, { data, n, padL, plotW, bw, events, completeThrough, padTop, plotH });

  function drawSeries(key, color) {
    const pts = [];
    const tip = buildTooltip(wrap);
    const dots = [];
    data.forEach((row, i) => {
      const v = row[key];
      if (v === null || v === undefined) return;
      const x = padL + i * bw + bw / 2;
      const y = yScale(Math.max(yMin, Math.min(yMax, v)));
      pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
      dots.push({ x, y, v, m: row.m });
    });
    if (pts.length > 1) svg.appendChild(el('polyline', { fill: 'none', stroke: color, 'stroke-width': 1.5, points: pts.join(' ') }));
    dots.forEach(({ x, y, v, m }) => {
      const c = el('circle', {
        cx: x, cy: y, r: 3, fill: color, tabindex: '0', role: 'img',
        'aria-label': `${monthLong(m)}: rating ${decFmt(v, 2)}`,
      });
      const show = (clientY) => {
        const rect = wrap.getBoundingClientRect();
        showTooltip(tip, wrap, x, (clientY ?? rect.top + 20) - rect.top, [monthLong(m), `Rating: ${decFmt(v, 2)}`]);
      };
      c.addEventListener('mouseenter', (e) => show(e.clientY));
      c.addEventListener('mousemove', (e) => show(e.clientY));
      c.addEventListener('mouseleave', () => hideTooltip(tip));
      c.addEventListener('focus', () => show(undefined));
      c.addEventListener('blur', () => hideTooltip(tip));
      svg.appendChild(c);
    });
  }
  if (channels.new) drawSeries('rating_new', cssVar('--graphite'));
  if (channels.renewed) drawSeries('rating_renewed', cssVar('--steel'));

  wrap.appendChild(svg);
  return wrap;
}

/**
 * Monthly average-rating line strip, months below `threshold` marked with an
 * orange dot.
 */
export function renderRatingStrip({ months, from, to, series = 'rating_new', threshold = 4.4, width = 980, height = 100 }) {
  const wrap = document.createElement('div');
  const data = monthsInRange(months, from, to);
  const n = data.length;
  const padL = 44;
  const padR = 16;
  const padTop = 10;
  const padBottom = 20;
  const plotW = width - padL - padR;
  const plotH = height - padTop - padBottom;
  const totalW = plotW + padL + padR;

  const svg = makeSvg(totalW, height, 'Average rating');

  const yMin = 4.0;
  const yMax = 5.0;
  const yScale = (v) => padTop + plotH - ((v - yMin) / (yMax - yMin)) * plotH;
  [4.0, 4.5, 5.0].forEach((v) => {
    const y = yScale(v);
    svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: y, y2: y, stroke: cssVar('--hairline') }));
    svg.appendChild(el('text', { x: padL - 8, y: y + 4, 'text-anchor': 'end', 'font-family': 'IBM Plex Mono', 'font-size': 11, fill: cssVar('--muted') })).textContent = decFmt(v, 2);
  });

  const bw = plotW / n;
  const pts = [];
  const lowPts = [];
  data.forEach((row, i) => {
    const v = row[series];
    if (v === null || v === undefined) return;
    const x = padL + i * bw + bw / 2;
    const y = yScale(Math.max(yMin, Math.min(yMax, v)));
    pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    if (v < threshold) lowPts.push({ x, y, v, m: row.m });
  });
  if (pts.length) {
    svg.appendChild(el('polyline', { fill: 'none', stroke: cssVar('--ink'), 'stroke-width': 1.5, points: pts.join(' ') }));
  }
  const tip = buildTooltip(wrap);
  lowPts.forEach(({ x, y, v, m }) => {
    const c = el('circle', { cx: x, cy: y, r: 4, fill: cssVar('--tag-orange'), tabindex: '0', role: 'img', 'aria-label': `${monthLong(m)}: rating ${decFmt(v, 2)}, below ${threshold}` });
    c.addEventListener('mouseenter', (e) => {
      const rect = wrap.getBoundingClientRect();
      showTooltip(tip, wrap, x, e.clientY - rect.top, [monthLong(m), `Rating: ${decFmt(v, 2)}`]);
    });
    c.addEventListener('mouseleave', () => hideTooltip(tip));
    c.addEventListener('focus', () => showTooltip(tip, wrap, x, 20, [monthLong(m), `Rating: ${decFmt(v, 2)}`]));
    c.addEventListener('blur', () => hideTooltip(tip));
    svg.appendChild(c);
  });

  wrap.appendChild(svg);
  return wrap;
}

/**
 * Event-study chart: product's monthly new-unit reviews from -window to
 * +window relative to the event month, with the comparison band (lo/hi area
 * + dashed mid line) when the event carries a `band`.
 */
export function renderEventStudyChart({ eventMonth, band, actualByOffset, windowSize, width = 900, height = 340, eventLabel }) {
  const wrap = document.createElement('div');
  const offsets = [];
  for (let r = -windowSize; r <= windowSize; r += 1) offsets.push(r);
  const padL = 44;
  const padR = 16;
  const padTop = 40;
  const padBottom = 28;
  const plotW = width - padL - padR;
  const plotH = height - padTop - padBottom;
  const totalW = plotW + padL + padR;

  const bandByOffset = new Map((band || []).map((b) => [b.r, b]));
  const allVals = offsets.map((r) => actualByOffset.get(r) ?? 0);
  (band || []).forEach((b) => { allVals.push(b.hi, b.lo, b.mid); });
  const maxVal = Math.max(1, ...allVals);
  const { step, niceMax } = niceStep(maxVal);
  const yScale = (v) => padTop + plotH - (v / niceMax) * plotH;
  const bw = plotW / offsets.length;

  const svg = makeSvg(totalW, height, 'Reviews relative to the event');

  for (let v = 0; v <= niceMax + 0.0001; v += step) {
    const y = yScale(v);
    svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: y, y2: y, stroke: cssVar('--hairline'), 'stroke-width': 1 }));
    svg.appendChild(el('text', { x: padL - 8, y: y + 4, 'text-anchor': 'end', 'font-family': 'IBM Plex Mono', 'font-size': 11, fill: cssVar('--muted') })).textContent = intFmt(v);
  }

  // comparison band (area between lo and hi) + dashed mid line
  if (band && band.length) {
    const areaTop = band.map((b) => `${(padL + (b.r + windowSize) * bw + bw / 2).toFixed(1)},${yScale(b.hi).toFixed(1)}`);
    const areaBottom = band.slice().reverse().map((b) => `${(padL + (b.r + windowSize) * bw + bw / 2).toFixed(1)},${yScale(b.lo).toFixed(1)}`);
    svg.appendChild(el('polygon', { points: [...areaTop, ...areaBottom].join(' '), fill: cssVar('--steel'), 'fill-opacity': 0.18, stroke: 'none' }));
    const midPts = band.map((b) => `${(padL + (b.r + windowSize) * bw + bw / 2).toFixed(1)},${yScale(b.mid).toFixed(1)}`);
    svg.appendChild(el('polyline', { points: midPts.join(' '), fill: 'none', stroke: cssVar('--muted'), 'stroke-width': 1.5, 'stroke-dasharray': '4 3' }));
  }

  // actual bars
  const barW = Math.max(2, bw * 0.72);
  const tip = buildTooltip(wrap);
  offsets.forEach((r, i) => {
    const v = actualByOffset.get(r);
    const x = padL + i * bw + (bw - barW) / 2;
    if (v !== undefined) {
      const h = (v / niceMax) * plotH;
      const signed = r > 0 ? `+${r}` : r < 0 ? `${MINUS}${Math.abs(r)}` : '0';
      const bar = el('rect', { x, y: padTop + plotH - h, width: barW, height: Math.max(h, v > 0 ? 0.6 : 0), fill: cssVar('--graphite'), tabindex: '0', role: 'img', 'aria-label': `${signed} months: ${intFmt(v)} reviews` });
      const show = (clientY) => {
        const rect = wrap.getBoundingClientRect();
        const lines = [`${signed} months from event`, `New-unit reviews: ${intFmt(v)}`];
        const b = bandByOffset.get(r);
        if (b) lines.push(`Comparison band: ${intFmt(b.lo)}–${intFmt(b.hi)}`);
        showTooltip(tip, wrap, x + barW / 2, (clientY ?? padTop + 20) - rect.top, lines);
      };
      bar.addEventListener('mouseenter', (e) => show(e.clientY));
      bar.addEventListener('mousemove', (e) => show(e.clientY));
      bar.addEventListener('mouseleave', () => hideTooltip(tip));
      bar.addEventListener('focus', () => show(undefined));
      bar.addEventListener('blur', () => hideTooltip(tip));
      svg.appendChild(bar);
    }
  });

  svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: padTop + plotH, y2: padTop + plotH, stroke: cssVar('--ink'), 'stroke-width': 1 }));

  // event line at offset 0
  const zeroIdx = offsets.indexOf(0);
  if (zeroIdx !== -1) {
    const x = padL + zeroIdx * bw + bw / 2;
    svg.appendChild(el('line', { x1: x, x2: x, y1: padTop, y2: padTop + plotH, stroke: cssVar('--tag-orange'), 'stroke-width': 1.5, 'stroke-dasharray': '3 3' }));
    const label = eventLabel || monthLong(eventMonth);
    const labelW = Math.min(Math.max(90, label.length * 6.2 + 12), 260);
    let labelX = x;
    if (labelX + labelW > padL + plotW) labelX = x - labelW - 4;
    if (labelX < padL) labelX = padL;
    svg.appendChild(el('rect', { x: labelX, y: padTop - 24, width: labelW, height: 18, fill: '#fff', stroke: cssVar('--tag-orange') }));
    const t = el('text', { x: labelX + 6, y: padTop - 11, 'font-family': 'IBM Plex Sans', 'font-size': 11, fill: cssVar('--ink') });
    t.textContent = label.length > 40 ? `${label.slice(0, 39)}…` : label;
    svg.appendChild(t);
  }

  // offset axis labels every few ticks
  const tickEvery = Math.ceil(offsets.length / 10) || 1;
  offsets.forEach((r, i) => {
    if (r % tickEvery === 0) {
      const x = padL + i * bw + bw / 2;
      const signed = r > 0 ? `+${r}` : r < 0 ? `${MINUS}${Math.abs(r)}` : '0';
      svg.appendChild(el('text', { x, y: padTop + plotH + 18, 'text-anchor': 'middle', 'font-family': 'IBM Plex Mono', 'font-size': 11, fill: cssVar('--muted') })).textContent = signed;
    }
  });

  wrap.appendChild(svg);
  return wrap;
}

/**
 * Generic categorical line chart: shared x axis of discrete categories
 * (age bands, years), one or more series of {value, at index i} points.
 * Used for the product life cycle chart and the two Findings line charts
 * (ratings-by-age and 1-2 star share-by-year). A series can mark a run of
 * trailing categories as "partial" (dashed, per house style for incomplete
 * data) via `dashedFrom`.
 */
export function renderCategoryLineChart({
  categories, series, yMin = 1, yMax = 5, yStep = 1, width = 640, height = 260,
  yFmt = (v) => decFmt(v, 1), dashedFrom = null, ariaLabel = 'Chart',
}) {
  const wrap = document.createElement('div');
  const n = categories.length;
  const padL = 44;
  const padR = 16;
  const padTop = 14;
  const padBottom = 28;
  const plotW = width - padL - padR;
  const plotH = height - padTop - padBottom;
  const totalW = plotW + padL + padR;
  const step = n > 1 ? plotW / (n - 1) : 0;
  const xAt = (i) => (n > 1 ? padL + i * step : padL + plotW / 2);
  const yScale = (v) => padTop + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

  const svg = makeSvg(totalW, height, ariaLabel);

  for (let v = yMin; v <= yMax + 0.0001; v += yStep) {
    const y = yScale(v);
    svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: y, y2: y, stroke: cssVar('--hairline'), 'stroke-width': 1 }));
    svg.appendChild(el('text', { x: padL - 8, y: y + 4, 'text-anchor': 'end', 'font-family': 'IBM Plex Mono', 'font-size': 11, fill: cssVar('--muted') })).textContent = yFmt(v);
  }
  svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: padTop + plotH, y2: padTop + plotH, stroke: cssVar('--ink'), 'stroke-width': 1 }));
  categories.forEach((c, i) => {
    const x = xAt(i);
    const dashed = dashedFrom !== null && i >= dashedFrom;
    svg.appendChild(el('text', {
      x, y: padTop + plotH + 18, 'text-anchor': n > 4 && String(c).length > 6 ? 'middle' : 'middle',
      'font-family': 'IBM Plex Mono', 'font-size': 10.5, fill: dashed ? cssVar('--muted') : cssVar('--muted'),
    })).textContent = String(c);
  });

  const tip = buildTooltip(wrap);
  for (const s of series) {
    const pts = [];
    const dashedPts = [];
    const dots = [];
    s.values.forEach((v, i) => {
      if (v === null || v === undefined) return;
      const x = xAt(i);
      const y = yScale(Math.max(yMin, Math.min(yMax, v)));
      const isDashed = dashedFrom !== null && i >= dashedFrom;
      (isDashed ? dashedPts : pts).push({ x, y });
      dots.push({ x, y, v, i, isDashed });
    });
    // Bridge the solid/dashed segments so the line reads continuously.
    if (dashedFrom !== null && pts.length && dashedPts.length) dashedPts.unshift(pts[pts.length - 1]);
    if (pts.length > 1) svg.appendChild(el('polyline', { fill: 'none', stroke: s.color, 'stroke-width': 2, points: pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') }));
    if (dashedPts.length > 1) svg.appendChild(el('polyline', { fill: 'none', stroke: s.color, 'stroke-width': 2, 'stroke-dasharray': '5 4', points: dashedPts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') }));
    dots.forEach(({ x, y, v, i }) => {
      const c = el('circle', { cx: x, cy: y, r: 3.2, fill: s.color, tabindex: '0', role: 'img', 'aria-label': `${s.label}, ${categories[i]}: ${yFmt(v)}` });
      const show = (clientY) => {
        const rect = wrap.getBoundingClientRect();
        showTooltip(tip, wrap, x, (clientY ?? rect.top + 20) - rect.top, [`${categories[i]}`, `${s.label}: ${yFmt(v)}`]);
      };
      c.addEventListener('mouseenter', (e) => show(e.clientY));
      c.addEventListener('mousemove', (e) => show(e.clientY));
      c.addEventListener('mouseleave', () => hideTooltip(tip));
      c.addEventListener('focus', () => show(undefined));
      c.addEventListener('blur', () => hideTooltip(tip));
      svg.appendChild(c);
    });
  }

  wrap.appendChild(svg);
  return wrap;
}

/**
 * Grouped vertical bar chart: one group per category, one square-cornered
 * bar per series within the group. Used for the stated-time-to-failure
 * bands and the refurbished/new arrival-complaint comparison.
 */
export function renderGroupedBarChart({ categories, series, width = 640, height = 280, valueFmt = (v) => intFmt(v), yFmt = (v) => intFmt(v), ariaLabel = 'Chart' }) {
  const wrap = document.createElement('div');
  const n = categories.length;
  const padL = 44;
  const padR = 16;
  const padTop = 14;
  const padBottom = 40;
  const plotW = width - padL - padR;
  const plotH = height - padTop - padBottom;
  const totalW = plotW + padL + padR;
  const groupW = plotW / n;
  const barGap = 4;
  const barW = Math.max(4, (groupW - barGap * (series.length + 1)) / series.length);

  const maxVal = Math.max(1, ...series.flatMap((s) => s.values.map((v) => v || 0)));
  const { step, niceMax } = niceStep(maxVal);
  const yScale = (v) => padTop + plotH - (v / niceMax) * plotH;

  const svg = makeSvg(totalW, height, ariaLabel);
  for (let v = 0; v <= niceMax + 0.0001; v += step) {
    const y = yScale(v);
    svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: y, y2: y, stroke: cssVar('--hairline'), 'stroke-width': 1 }));
    svg.appendChild(el('text', { x: padL - 8, y: y + 4, 'text-anchor': 'end', 'font-family': 'IBM Plex Mono', 'font-size': 11, fill: cssVar('--muted') })).textContent = yFmt(v);
  }
  svg.appendChild(el('line', { x1: padL, x2: padL + plotW, y1: padTop + plotH, y2: padTop + plotH, stroke: cssVar('--ink'), 'stroke-width': 1 }));

  const tip = buildTooltip(wrap);
  categories.forEach((cat, gi) => {
    const groupX = padL + gi * groupW;
    series.forEach((s, si) => {
      const v = s.values[gi] || 0;
      const h = (v / niceMax) * plotH;
      const x = groupX + barGap + si * (barW + barGap);
      const bar = el('rect', {
        x, y: padTop + plotH - h, width: barW, height: Math.max(h, v > 0 ? 0.6 : 0), fill: s.color,
        tabindex: '0', role: 'img', 'aria-label': `${cat}, ${s.label}: ${valueFmt(v)}`,
      });
      const show = (clientY) => {
        const rect = wrap.getBoundingClientRect();
        showTooltip(tip, wrap, x + barW / 2, (clientY ?? padTop + 20) - rect.top, [cat, `${s.label}: ${valueFmt(v)}`]);
      };
      bar.addEventListener('mouseenter', (e) => show(e.clientY));
      bar.addEventListener('mousemove', (e) => show(e.clientY));
      bar.addEventListener('mouseleave', () => hideTooltip(tip));
      bar.addEventListener('focus', () => show(undefined));
      bar.addEventListener('blur', () => hideTooltip(tip));
      svg.appendChild(bar);
    });
    // Category labels wrap onto a second line at a word boundary instead of being cut off.
    const label = String(cat);
    const maxChars = Math.max(8, Math.floor(groupW / 6.5));
    let lines = [label];
    if (label.length > maxChars && label.includes(' ')) {
      const words = label.split(' ');
      let first = '';
      while (words.length && (first + ' ' + words[0]).trim().length <= maxChars) first = `${first} ${words.shift()}`.trim();
      lines = [first || words.shift(), words.join(' ')].filter(Boolean);
    }
    const text = svg.appendChild(el('text', {
      x: groupX + groupW / 2, y: padTop + plotH + 16, 'text-anchor': 'middle',
      'font-family': 'IBM Plex Sans', 'font-size': 11, fill: cssVar('--muted'),
    }));
    lines.forEach((ln, i) => {
      text.appendChild(el('tspan', { x: groupX + groupW / 2, dy: i === 0 ? 0 : 13 })).textContent = ln;
    });
  });

  wrap.appendChild(svg);
  return wrap;
}
