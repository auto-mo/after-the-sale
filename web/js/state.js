// Shared, in-memory application state. Nothing here is persisted except the
// one-time tour flag (localStorage, wrapped in try/catch per the spec).

const bus = new EventTarget();

/** Current "view" the chat/UI can read and set: which product, what window,
 * which channels, and volume vs rating. This is the single source of truth
 * the chat drawer's `view` payload maps onto. */
export const view = {
  productId: null, // set once from portfolio.default_product before the router's first render
  from: null, // month string, filled in once the product loads
  to: null,
  channels: { new: true, renewed: true },
  measure: 'volume', // 'volume' | 'rating'
};

let previousView = null;

/** Called once at boot with portfolio.default_product. Never overrides a
 * product already chosen (e.g. by a deep link resolved first). Goes through
 * setView so anything already listening (the picker's button label) picks it
 * up even if it rendered before the default arrived. */
export function ensureDefaultProduct(id) {
  if (!view.productId) setView({ productId: id });
}

export function getView() {
  return { productId: view.productId, from: view.from, to: view.to, channels: { ...view.channels }, measure: view.measure };
}

/** Merge a partial view and notify listeners. Set `remember` to snapshot the
 * prior view first, so a chat "Undo" can restore it. */
export function setView(partial, { remember = false } = {}) {
  if (remember) previousView = getView();
  if (partial.productId !== undefined) view.productId = partial.productId;
  if (partial.from !== undefined) view.from = partial.from;
  if (partial.to !== undefined) view.to = partial.to;
  if (partial.channels !== undefined) view.channels = { ...view.channels, ...partial.channels };
  if (partial.measure !== undefined) view.measure = partial.measure;
  bus.dispatchEvent(new CustomEvent('view:changed', { detail: getView() }));
}

export function getPreviousView() {
  return previousView;
}

export function onViewChanged(handler) {
  bus.addEventListener('view:changed', handler);
  return () => bus.removeEventListener('view:changed', handler);
}

const TOUR_KEY = 'de-tour-done';

export function isTourDone() {
  try {
    return window.localStorage.getItem(TOUR_KEY) === '1';
  } catch {
    return false;
  }
}

export function markTourDone() {
  try {
    window.localStorage.setItem(TOUR_KEY, '1');
  } catch {
    /* ignore */
  }
}
