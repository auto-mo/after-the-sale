import { loadPortfolio } from '../data.js?v=202609232353';
import { intFmt, pctFmt, rangeFmt, decFmt, monthShort } from '../format.js?v=202609232353';

const CASE_GROUP_LABEL = {
  sibling_launch: 'Sibling launch',
  refurbished: 'Refurbished units appear',
  low_rating: 'Low-rating month',
};

const CASE_HEADLINE = {
  sibling_launch: { down: 'Largest drops after a sibling launched: possible cannibalisation', up: 'Largest rises after a sibling launched' },
  refurbished: { down: 'Largest drops after refurbished units appeared', up: 'Largest rises after refurbished units appeared' },
  low_rating: { down: 'Largest drops after a low-rating month', up: 'Largest rises after a low-rating month' },
};

const ROWS_COLLAPSED = 5;

function shortTitle(title, max = 64) {
  if (!title || title.length <= max) return title || '';
  return `${title.slice(0, max - 1).trimEnd()}…`;
}

const QUESTIONS = [
  {
    type: 'sibling_launch',
    question: 'Does a sibling model launching in the same family move an older product’s reviews?',
    headline: (pooled) => `Older products' reviews ran about ${decFmt(Math.abs(pooled.avg_effect_pct), 0)}% ${pooled.avg_effect_pct >= 0 ? 'higher' : 'lower'} after a sibling launched`,
    explain: 'That is more consistent with a family halo, or with launches being timed when a line is already growing, than with the new model cannibalising the old one. The data shows the two happening together and cannot say which caused which.',
  },
  {
    type: 'refurbished',
    question: 'Do refurbished (Amazon Renewed) listings move new-unit reviews?',
    headline: (pooled) => `New-unit reviews ran about ${decFmt(Math.abs(pooled.avg_effect_pct), 0)}% ${pooled.avg_effect_pct >= 0 ? 'higher' : 'lower'} once refurbished units appeared`,
    explain: 'Refurbished units tend to show up once a product has already sold a lot, because more sales means more returns feeding the Renewed channel. So this is most likely about timing, and it does not show that refurbished sales help new-unit demand.',
  },
  {
    type: 'low_rating',
    question: 'Does a run of low ratings move the reviews that follow?',
    headline: (pooled) => `Reviews ran about ${decFmt(Math.abs(pooled.avg_effect_pct), 0)}% ${pooled.avg_effect_pct >= 0 ? 'higher' : 'lower'} in the ${pooled.window} months after a low-rating month`,
    explain: 'The effect is small, and some of the months tested overlap market-wide shifts such as spring 2020.',
  },
];

function verdictTag(pooled) {
  const wrap = document.createElement('span');
  wrap.className = `verdict-tag verdict-lg${pooled.verdict === 'not_enough_data' ? ' verdict-not-enough' : ''}`;
  const punch = document.createElement('span');
  punch.className = 'verdict-punch';
  const label = document.createElement('span');
  label.className = 'verdict-label';
  if (pooled.verdict === 'moved') label.textContent = pooled.avg_effect_pct < 0 ? 'Moved down' : 'Moved up';
  else if (pooled.verdict === 'no_clear_change') label.textContent = 'No clear change';
  else label.textContent = 'Not enough data';
  wrap.appendChild(punch);
  wrap.appendChild(label);
  return wrap;
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
  container.innerHTML = '';

  const h1 = document.createElement('h1');
  h1.style.marginBottom = '18px';
  h1.textContent = 'Averaged across hundreds of events, three patterns hold up';
  container.appendChild(h1);

  for (const q of QUESTIONS) {
    const pooled = portfolio.pooled.find((p) => p.event_type === q.type);
    const section = document.createElement('section');
    section.className = 'findings-question';
    const head = document.createElement('div');
    head.className = 'fq-head';
    const headText = document.createElement('div');
    const h2 = document.createElement('h2');
    h2.textContent = pooled ? q.headline(pooled) : q.question;
    headText.appendChild(h2);
    const subtitle = document.createElement('p');
    subtitle.className = 'findings-subtitle';
    subtitle.textContent = q.question;
    headText.appendChild(subtitle);
    head.appendChild(headText);
    if (pooled) head.appendChild(verdictTag(pooled));
    section.appendChild(head);

    if (pooled) {
      const meta = document.createElement('p');
      meta.className = 'findings-meta';
      meta.textContent = `Across ${intFmt(pooled.n_events)} events on ${intFmt(pooled.n_products)} products, tested with a ±${pooled.window}-month window: reviews ran ${pctFmt(pooled.avg_effect_pct)} versus comparison on average (${rangeFmt(pooled.lo_pct, pooled.hi_pct)}).`;
      section.appendChild(meta);
    }

    const explain = document.createElement('p');
    explain.className = 'findings-explain';
    explain.textContent = q.explain;
    section.appendChild(explain);

    container.appendChild(section);
  }

  const closing = document.createElement('p');
  closing.className = 'findings-closing';
  const tested = portfolio.stats.events_tested;
  closing.textContent = `Single events are not detectable: 0 of ${intFmt(tested)} survive the false-discovery check applied across every event tested. A fake-date test, run on 3,868 events with no real event behind them, found the method would call a single event "Moved" about 1 time in 10 by chance alone. The averages above, pooled across hundreds of events, are the level at which this data can support a claim.`;
  container.appendChild(closing);

  if (portfolio.cases) renderCases(container, portfolio.cases, portfolio.cases_note);
}

function renderCases(container, cases, note) {
  const section = document.createElement('section');
  section.style.marginTop = '32px';

  const h2 = document.createElement('h2');
  h2.style.marginBottom = '8px';
  h2.textContent = 'Cases worth a closer look';
  section.appendChild(h2);

  if (note) {
    const p = document.createElement('p');
    p.className = 'findings-meta';
    p.style.marginBottom = '18px';
    p.textContent = note;
    section.appendChild(p);
  }

  for (const type of ['sibling_launch', 'refurbished', 'low_rating']) {
    const group = cases[type];
    if (!group) continue;
    section.appendChild(renderCaseGroup(type, group));
  }

  container.appendChild(section);
}

function renderCaseGroup(type, group) {
  const wrap = document.createElement('div');
  wrap.className = 'case-group';

  const h3 = document.createElement('h3');
  h3.textContent = CASE_GROUP_LABEL[type] || type;
  wrap.appendChild(h3);

  const segRow = document.createElement('div');
  segRow.className = 'segmented';
  segRow.setAttribute('role', 'tablist');
  segRow.setAttribute('aria-label', `${CASE_GROUP_LABEL[type]} direction`);
  const dropsBtn = document.createElement('button');
  dropsBtn.type = 'button';
  dropsBtn.className = 'segmented-btn active';
  dropsBtn.textContent = 'Largest drops';
  dropsBtn.setAttribute('role', 'tab');
  dropsBtn.setAttribute('aria-selected', 'true');
  const risesBtn = document.createElement('button');
  risesBtn.type = 'button';
  risesBtn.className = 'segmented-btn';
  risesBtn.textContent = 'Largest rises';
  risesBtn.setAttribute('role', 'tab');
  risesBtn.setAttribute('aria-selected', 'false');
  segRow.appendChild(dropsBtn);
  segRow.appendChild(risesBtn);
  wrap.appendChild(segRow);

  const headline = document.createElement('p');
  headline.className = 'case-headline';
  wrap.appendChild(headline);

  const list = document.createElement('div');
  list.className = 'case-list';
  wrap.appendChild(list);

  const moreBtn = document.createElement('button');
  moreBtn.type = 'button';
  moreBtn.className = 'btn btn-ghost case-more';
  wrap.appendChild(moreBtn);

  let direction = 'down';
  let expanded = false;

  function draw() {
    const rows = group[direction] || [];
    headline.textContent = CASE_HEADLINE[type][direction];
    const shown = expanded ? rows : rows.slice(0, ROWS_COLLAPSED);
    list.innerHTML = '';
    for (const c of shown) list.appendChild(renderCaseRow(c));
    if (rows.length > ROWS_COLLAPSED) {
      moreBtn.hidden = false;
      moreBtn.textContent = expanded ? 'Show fewer' : `Show ${rows.length - ROWS_COLLAPSED} more`;
    } else {
      moreBtn.hidden = true;
    }
  }

  dropsBtn.addEventListener('click', () => {
    direction = 'down'; expanded = false;
    dropsBtn.classList.add('active'); dropsBtn.setAttribute('aria-selected', 'true');
    risesBtn.classList.remove('active'); risesBtn.setAttribute('aria-selected', 'false');
    draw();
  });
  risesBtn.addEventListener('click', () => {
    direction = 'up'; expanded = false;
    risesBtn.classList.add('active'); risesBtn.setAttribute('aria-selected', 'true');
    dropsBtn.classList.remove('active'); dropsBtn.setAttribute('aria-selected', 'false');
    draw();
  });
  moreBtn.addEventListener('click', () => { expanded = !expanded; draw(); });

  draw();
  return wrap;
}

function renderCaseRow(c) {
  const row = document.createElement('div');
  row.className = 'case-row';

  const info = document.createElement('div');
  info.className = 'case-info';
  info.innerHTML = `
    <span class="case-model">${c.model || c.product_id}</span>
    <span class="case-title">${shortTitle(c.title)}</span>
    <span class="case-month">${monthShort(c.month)}</span>
    ${c.near_zero_after ? '<span class="case-flag">possible discontinuation</span>' : ''}
  `;
  row.appendChild(info);

  const change = document.createElement('div');
  change.className = 'case-change';
  const val = document.createElement('span');
  val.className = 'mono case-change-value';
  val.textContent = pctFmt(c.effect_pct);
  const range = document.createElement('span');
  range.className = 'mono case-change-range';
  range.textContent = rangeFmt(c.lo_pct, c.hi_pct);
  change.appendChild(val);
  change.appendChild(range);
  row.appendChild(change);

  const link = document.createElement('a');
  link.className = 'event-link';
  link.href = `#/event/${c.product_id}/${c.event_id}`;
  link.textContent = 'Open the evidence';
  row.appendChild(link);

  return row;
}
