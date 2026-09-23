import { initRouter, registerRoute } from './js/router.js?v=202609232241';
import { initPicker } from './js/picker.js?v=202609232241';
import { initChat } from './js/chat.js?v=202609232241';
import { initTour, startTour, maybeAutoStart } from './js/tour.js?v=202609232241';
import { loadPortfolio } from './js/data.js?v=202609232241';
import { monthLong } from './js/format.js?v=202609232241';
import * as portfolioPage from './js/pages/portfolio.js?v=202609232241';
import * as productPage from './js/pages/product.js?v=202609232241';
import * as eventPage from './js/pages/event.js?v=202609232241';
import * as findingsPage from './js/pages/findings.js?v=202609232241';
import * as methodPage from './js/pages/method.js?v=202609232241';
import { view } from './js/state.js?v=202609232241';

registerRoute('/', portfolioPage.render);
registerRoute('/product', (root) => productPage.render(root, { id: view.productId }));
registerRoute('/product/:id', productPage.render);
registerRoute('/event/:productId/:eventId', eventPage.render);
registerRoute('/findings', findingsPage.render);
registerRoute('/method', methodPage.render);

const pageRoot = document.getElementById('page-root');
const pickerRoot = document.getElementById('picker-root');
const chatRoot = document.getElementById('chat-root');
const tourRoot = document.getElementById('tour-root');
const askBtn = document.getElementById('ask-btn');
const tourBtn = document.getElementById('tour-btn');

initPicker(pickerRoot);
initChat(chatRoot, askBtn);
initTour(tourRoot);
initRouter({ root: pageRoot, navSelector: '.site-nav a' });

tourBtn.addEventListener('click', () => startTour());

loadPortfolio().then((portfolio) => {
  const el = document.getElementById('footer-complete-through');
  if (el) el.textContent = monthLong(portfolio.complete_through);
}).catch(() => { /* footer keeps its static fallback text */ });

maybeAutoStart();
