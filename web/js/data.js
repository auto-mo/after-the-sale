// Data access layer. Reads only from web/data/*.json (generated, read-only).
// Every number shown in the UI must trace back to one of these files, or to
// the chat API response.

const cache = {
  products: null,
  portfolio: null,
  productDetail: new Map(), // id -> detail json (or {noData:true})
};

// Version appended to data URLs so a redeploy is not hidden by the CDN cache (set by scripts/stamp_version.py).
export const DATA_VERSION = '202609232241';

async function fetchJson(path) {
  const res = await fetch(`${path}?v=${DATA_VERSION}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.json();
}

/** Array of product summaries from products.json. */
export async function loadProducts() {
  if (!cache.products) {
    cache.products = fetchJson('data/products.json').catch((err) => {
      cache.products = null;
      throw err;
    });
  }
  return cache.products;
}

/** Portfolio-level rollups from portfolio.json. */
export async function loadPortfolio() {
  if (!cache.portfolio) {
    cache.portfolio = fetchJson('data/portfolio.json').catch((err) => {
      cache.portfolio = null;
      throw err;
    });
  }
  return cache.portfolio;
}

/** Find a product summary by id. */
export async function findProduct(id) {
  const products = await loadProducts();
  return products.find((p) => p.id === id) || null;
}

/**
 * Load the per-product detail file. Returns { product, detail } where
 * detail is null when the product has no reviews (and so no data file).
 * Throws only on a genuine fetch failure (network/server error), not on the
 * documented "no reviews" case.
 */
export async function loadProductDetail(id) {
  if (cache.productDetail.has(id)) {
    return cache.productDetail.get(id);
  }
  const product = await findProduct(id);
  if (!product) {
    const result = { product: null, detail: null, notFound: true };
    cache.productDetail.set(id, result);
    return result;
  }
  // Five products in the data have no reviews and so no file on disk (404).
  let res;
  try {
    res = await fetch(`data/p/${product.file}?v=${DATA_VERSION}`, { cache: 'no-store' });
  } catch (err) {
    throw new Error(`Could not reach data/p/${product.file}: ${err.message}`);
  }
  if (res.status === 404) {
    const result = { product, detail: null, notFound: false };
    cache.productDetail.set(id, result);
    return result;
  }
  if (!res.ok) throw new Error(`Failed to load data/p/${product.file}: ${res.status}`);
  const detail = await res.json();
  const result = { product, detail, notFound: false };
  cache.productDetail.set(id, result);
  return result;
}
