import { view, markTourDone } from './state.js?v=202609241638';
import { navigate } from './router.js?v=202609241638';

const STEPS = [
  {
    selector: '#picker-root .picker-btn',
    title: 'Pick a product',
    text: 'Search or browse every Shark and Ninja product here. Results are grouped by family.',
  },
  {
    selector: '.controls-row',
    title: 'Choose the window and what to show',
    text: 'Show new units, refurbished, or both, pick the date range, and switch between average rating and review volume.',
  },
  {
    selector: '.chart-card',
    title: 'Read the timeline',
    text: 'Rating is the default view. The hatched area is data collected after March 2023, and is incomplete.',
  },
  {
    selector: '.product-rail',
    title: 'What owners report',
    text: 'Complaint mix, quotes, a year by year table and how ratings change over the product’s life, each compared with the SharkNinja and peer averages for this type.',
  },
  {
    selector: '#ask-btn',
    title: 'Ask the assistant',
    text: 'It can rank products by complaints, explain a product’s numbers, and find products whose complaints jumped in one year. Suggested prompts are one click.',
  },
];

let root, dim, cutout, card;
let stepIndex = 0;
let active = false;
let lastFocused = null;
let resizeHandler = null;

function waitForRouteChange() {
  return new Promise((resolve) => {
    window.addEventListener('app:routechanged', () => resolve(), { once: true });
  });
}

function waitFrame() {
  return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}

function findTarget(selector) {
  return document.querySelector(selector);
}

function positionOn(target) {
  const rect = target.getBoundingClientRect();
  const pad = 6;
  cutout.style.left = `${rect.left - pad}px`;
  cutout.style.top = `${rect.top - pad}px`;
  cutout.style.width = `${rect.width + pad * 2}px`;
  cutout.style.height = `${rect.height + pad * 2}px`;
  cutout.hidden = false;

  const cardW = 380;
  let left = rect.left;
  let top = rect.bottom + 16;
  if (top + 220 > window.innerHeight) top = Math.max(16, rect.top - 220);
  if (left + cardW > window.innerWidth - 16) left = window.innerWidth - cardW - 16;
  if (left < 16) left = 16;
  card.style.left = `${left}px`;
  card.style.top = `${top}px`;
}

function renderStep() {
  const step = STEPS[stepIndex];
  const target = findTarget(step.selector);
  if (!target) {
    // target not on this page (shouldn't happen given navigation, but be safe)
    next();
    return;
  }
  target.scrollIntoView({ block: 'center', behavior: 'auto' });
  positionOn(target);

  card.innerHTML = `
    <span class="tour-step-label">Step ${stepIndex + 1} of ${STEPS.length}</span>
    <h2 id="tour-h">${step.title}</h2>
    <p>${step.text}</p>
    ${step.sub ? `<p class="tour-sub">${step.sub}</p>` : ''}
    <div class="tour-footer">
      <div class="tour-dots" aria-hidden="true">
        ${STEPS.map((_, i) => `<span class="tour-dot${i === stepIndex ? ' active' : ''}"></span>`).join('')}
      </div>
      <div class="tour-actions">
        <button type="button" id="tour-skip" class="btn btn-ghost">Skip tour</button>
        ${stepIndex > 0 ? '<button type="button" id="tour-back" class="btn btn-ghost">Back</button>' : ''}
        <button type="button" id="tour-next" class="btn btn-primary">${stepIndex === STEPS.length - 1 ? 'Done' : 'Next'}</button>
      </div>
    </div>
  `;
  card.querySelector('#tour-skip').addEventListener('click', stop);
  card.querySelector('#tour-next').addEventListener('click', next);
  const backBtn = card.querySelector('#tour-back');
  if (backBtn) backBtn.addEventListener('click', back);
  card.querySelector('#tour-next').focus();
}

function next() {
  if (stepIndex >= STEPS.length - 1) { stop(); return; }
  stepIndex += 1;
  renderStep();
}

function back() {
  if (stepIndex <= 0) return;
  stepIndex -= 1;
  renderStep();
}

function onKeydown(e) {
  if (e.key === 'Escape') stop();
}

function stop() {
  if (!active) return;
  active = false;
  markTourDone();
  dim.hidden = true;
  cutout.hidden = true;
  card.hidden = true;
  document.removeEventListener('keydown', onKeydown);
  if (resizeHandler) window.removeEventListener('resize', resizeHandler);
  if (lastFocused && lastFocused.focus) lastFocused.focus();
}

export function initTour(rootEl) {
  root = rootEl;
  root.innerHTML = `
    <div class="tour-dim" id="tour-dim" hidden></div>
    <div class="tour-cutout" id="tour-cutout" hidden></div>
    <div class="tour-card" id="tour-card" role="dialog" aria-modal="true" aria-labelledby="tour-h" hidden></div>
  `;
  dim = root.querySelector('#tour-dim');
  cutout = root.querySelector('#tour-cutout');
  card = root.querySelector('#tour-card');
}

export async function startTour() {
  lastFocused = document.activeElement;
  active = true;
  stepIndex = 0;
  dim.hidden = false;
  card.hidden = false;
  document.addEventListener('keydown', onKeydown);
  resizeHandler = () => {
    const step = STEPS[stepIndex];
    const target = findTarget(step.selector);
    if (target) positionOn(target);
  };
  window.addEventListener('resize', resizeHandler);

  const needsProductPage = !window.location.hash.startsWith('#/product');
  if (needsProductPage) {
    const routeChanged = waitForRouteChange();
    navigate(`/product/${view.productId}`);
    await routeChanged;
  }
  await waitFrame();
  renderStep();
}
