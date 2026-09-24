// Light/dark theme toggle. Persists the explicit choice; otherwise follows
// the OS preference. Wrapped in try/catch per house style (private window,
// blocked storage).

const KEY = 'ats-theme';

function stored() {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function store(v) {
  try {
    window.localStorage.setItem(KEY, v);
  } catch {
    /* ignore */
  }
}

export function currentTheme() {
  return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
}

function apply(theme) {
  document.documentElement.setAttribute('data-theme', theme);
}

export function initTheme(onChange) {
  const saved = stored();
  const system = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  apply(saved || system);
  if (typeof onChange === 'function') onChange(currentTheme());
}

export function toggleTheme(onChange) {
  const next = currentTheme() === 'dark' ? 'light' : 'dark';
  apply(next);
  store(next);
  if (typeof onChange === 'function') onChange(next);
}
