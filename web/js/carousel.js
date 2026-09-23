// Intro carousel: a centered modal shown before the pointing tour, on first
// visit only (same localStorage flag as the tour; `?notour` skips both).

import { isTourDone, markTourDone } from './state.js?v=202609232353';

const CARDS = [
  {
    title: 'What this is',
    body: "Demand Evidence looks at what moved a Shark or Ninja product's demand on Amazon, and what did not.",
  },
  {
    title: 'The data',
    body: 'Written Amazon reviews and star ratings from 2002 to March 2023: about 290,000 reviews across 1,138 products. Review volume stands in for demand.',
  },
  {
    title: 'Where it comes from',
    body: 'Amazon Reviews 2023, a public research dataset from the McAuley Lab at UC San Diego. It has no sales, price, stock or seller data.',
  },
  {
    title: 'What it can show',
    body: "How a product's reviews and ratings moved around three kinds of event: a sibling model launching, refurbished units appearing, and a month of low ratings. Also the patterns that hold across hundreds of events, and real cases worth a closer look.",
  },
  {
    title: 'What it cannot',
    body: 'Why something happened. Results show what moved together, and a single event is usually too noisy to call on its own.',
  },
];

let root;
let dim;
let card;
let index = 0;
let lastFocused = null;
let onFinishCb = null;

function focusableEls() {
  return [...card.querySelectorAll('button')].filter((el) => !el.disabled);
}

function onKeydown(e) {
  if (e.key === 'Escape') {
    e.preventDefault();
    close({ finish: false });
    return;
  }
  if (e.key === 'Tab') {
    const els = focusableEls();
    if (!els.length) return;
    const first = els[0];
    const last = els[els.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
}

function render() {
  const c = CARDS[index];
  const isLast = index === CARDS.length - 1;
  card.innerHTML = `
    <span class="tour-step-label">Step ${index + 1} of ${CARDS.length}</span>
    <h2 id="carousel-h">${c.title}</h2>
    <p>${c.body}</p>
    <div class="tour-footer">
      <div class="tour-dots" aria-hidden="true">
        ${CARDS.map((_, i) => `<span class="tour-dot${i === index ? ' active' : ''}"></span>`).join('')}
      </div>
      <div class="tour-actions">
        <button type="button" id="car-skip" class="btn btn-ghost">Skip</button>
        ${index > 0 ? '<button type="button" id="car-back" class="btn btn-ghost">Back</button>' : ''}
        <button type="button" id="car-next" class="btn btn-primary">${isLast ? 'Start the tour' : 'Next'}</button>
      </div>
    </div>
  `;
  card.querySelector('#car-skip').addEventListener('click', () => close({ finish: false }));
  const backBtn = card.querySelector('#car-back');
  if (backBtn) backBtn.addEventListener('click', back);
  card.querySelector('#car-next').addEventListener('click', () => {
    if (isLast) close({ finish: true });
    else next();
  });
  card.querySelector('#car-next').focus();
}

function next() {
  if (index >= CARDS.length - 1) return;
  index += 1;
  render();
}

function back() {
  if (index <= 0) return;
  index -= 1;
  render();
}

function close({ finish }) {
  markTourDone();
  dim.hidden = true;
  card.hidden = true;
  document.removeEventListener('keydown', onKeydown);
  if (finish && typeof onFinishCb === 'function') {
    onFinishCb();
  } else if (lastFocused && lastFocused.focus) {
    lastFocused.focus();
  }
}

export function initCarousel(rootEl, { onFinish } = {}) {
  root = rootEl;
  onFinishCb = onFinish || null;
  root.innerHTML = `
    <div class="tour-dim" id="carousel-dim" hidden></div>
    <div class="tour-card carousel-card" id="carousel-card" role="dialog" aria-modal="true" aria-labelledby="carousel-h" hidden></div>
  `;
  dim = root.querySelector('#carousel-dim');
  card = root.querySelector('#carousel-card');
}

export function startCarousel() {
  index = 0;
  lastFocused = document.activeElement;
  dim.hidden = false;
  card.hidden = false;
  document.addEventListener('keydown', onKeydown);
  render();
}

export function maybeAutoStartCarousel() {
  if (isTourDone() || new URLSearchParams(location.search).has('notour')) return;
  setTimeout(() => startCarousel(), 400);
}
