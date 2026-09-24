import { initRouter, registerRoute, navigate, rerenderCurrent } from './js/router.js?v=202609241634';
import { initPicker } from './js/picker.js?v=202609241634';
import { initChat } from './js/chat.js?v=202609241634';
import { initTour, startTour } from './js/tour.js?v=202609241634';
import { initCarousel, startCarousel, maybeAutoStartCarousel } from './js/carousel.js?v=202609241634';
import { loadPortfolio } from './js/data.js?v=202609241634';
import { monthLong } from './js/format.js?v=202609241634';
import { initTheme, toggleTheme } from './js/theme.js?v=202609241634';
import * as overviewPage from './js/pages/portfolio.js?v=202609241634';
import * as productPage from './js/pages/product.js?v=202609241634';
import * as findingsPage from './js/pages/findings.js?v=202609241634';
import * as methodPage from './js/pages/method.js?v=202609241634';
import { view, ensureDefaultProduct } from './js/state.js?v=202609241634';

registerRoute('/', overviewPage.render);
registerRoute('/product', (root) => productPage.render(root, { id: view.productId }));
registerRoute('/product/:id', productPage.render);
// The old event page is gone; any bookmarked link lands on the product it was about.
registerRoute('/event/:productId/:eventId', (root, params) => {
  navigate(`/product/${params.productId}`);
  root.innerHTML = '';
});
registerRoute('/findings', findingsPage.render);
registerRoute('/method', methodPage.render);

const pageRoot = document.getElementById('page-root');
const pickerRoot = document.getElementById('picker-root');
const chatRoot = document.getElementById('chat-root');
const tourRoot = document.getElementById('tour-root');
const carouselRoot = document.getElementById('carousel-root');
const askBtn = document.getElementById('ask-btn');
const tourBtn = document.getElementById('tour-btn');
const themeBtn = document.getElementById('theme-toggle');

initPicker(pickerRoot);
initChat(chatRoot, askBtn);
initTour(tourRoot);
initCarousel(carouselRoot, { onFinish: startTour });

function onThemeChanged(theme) {
  themeBtn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
}
initTheme(onThemeChanged);
themeBtn.addEventListener('click', () => {
  toggleTheme(onThemeChanged);
  rerenderCurrent(); // chart colors are read from CSS custom properties at draw time
});

async function boot() {
  let portfolio = null;
  try {
    portfolio = await loadPortfolio();
    ensureDefaultProduct(portfolio.default_product);
  } catch {
    ensureDefaultProduct('SN-AF101'); // last-resort fallback if the data file cannot be reached
  }

  initRouter({ root: pageRoot, navSelector: '.site-nav a' });

  if (portfolio) {
    const el = document.getElementById('footer-complete-through');
    if (el) el.textContent = monthLong(portfolio.complete_through);
  }

  maybeAutoStartCarousel();
}

tourBtn.addEventListener('click', () => startCarousel());

boot();
