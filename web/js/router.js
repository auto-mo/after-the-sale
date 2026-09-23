// Minimal hash router. Each page module exports an async render(container,
// params) that returns an optional cleanup function.

let pageRoot = null;
let navLinks = [];
let currentCleanup = null;
const routes = [];

export function registerRoute(pattern, loader) {
  // pattern like '/product/:id' -> regex with named groups
  const paramNames = [];
  const regexStr = pattern
    .split('/')
    .map((seg) => {
      if (seg.startsWith(':')) {
        paramNames.push(seg.slice(1));
        return '([^/]+)';
      }
      return seg.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    })
    .join('/');
  routes.push({ regex: new RegExp(`^${regexStr}$`), paramNames, loader });
}

function parseHash() {
  let hash = window.location.hash || '#/';
  hash = hash.slice(1); // drop '#'
  if (!hash.startsWith('/')) hash = `/${hash}`;
  const [path] = hash.split('?');
  return path.replace(/\/+$/, '') || '/';
}

function matchRoute(path) {
  for (const route of routes) {
    const m = route.regex.exec(path);
    if (m) {
      const params = {};
      route.paramNames.forEach((name, i) => { params[name] = decodeURIComponent(m[i + 1]); });
      return { loader: route.loader, params };
    }
  }
  return null;
}

function updateNavActive(path) {
  const topSegment = `/${path.split('/')[1] || ''}`;
  navLinks.forEach((a) => {
    const route = a.dataset.route;
    const active = route === '/' ? path === '/' : topSegment === route;
    a.classList.toggle('active', active);
  });
}

async function renderCurrent() {
  const path = parseHash();
  const match = matchRoute(path);
  if (typeof currentCleanup === 'function') {
    try { currentCleanup(); } catch { /* ignore */ }
  }
  currentCleanup = null;
  updateNavActive(path);
  pageRoot.innerHTML = '';
  if (!match) {
    pageRoot.innerHTML = '<div class="empty-state">Page not found.</div>';
    return;
  }
  try {
    const cleanup = await match.loader(pageRoot, match.params);
    if (typeof cleanup === 'function') currentCleanup = cleanup;
  } catch (err) {
    console.error(err);
    pageRoot.innerHTML = `<div class="error-state">Something went wrong loading this page. ${err && err.message ? err.message : ''}</div>`;
  }
  // Move focus for screen readers without letting the browser scroll the page under the sticky header.
  pageRoot.focus({ preventScroll: true });
  window.scrollTo(0, 0);
  window.dispatchEvent(new CustomEvent('app:routechanged'));
}

export function navigate(path) {
  window.location.hash = `#${path}`;
}

export function initRouter({ root, navSelector }) {
  pageRoot = root;
  navLinks = [...document.querySelectorAll(navSelector)];
  window.addEventListener('hashchange', renderCurrent);
  renderCurrent();
}
