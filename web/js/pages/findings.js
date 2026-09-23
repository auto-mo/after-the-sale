import { loadPortfolio } from '../data.js?v=202609232243';
import { intFmt, pctFmt, rangeFmt, decFmt } from '../format.js?v=202609232243';

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
}
