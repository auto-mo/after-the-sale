import { loadPortfolio } from '../data.js?v=202609240159';
import { intFmt, decFmt } from '../format.js?v=202609240159';

function themeRows(portfolio) {
  const groups = new Map();
  for (const t of portfolio.themes) {
    if (!groups.has(t.group)) groups.set(t.group, []);
    groups.get(t.group).push(t);
  }
  let rows = '';
  for (const [group, themes] of groups) {
    rows += `<tr><td colspan="4" style="font-weight:600;background:var(--paper)">${group}</td></tr>`;
    for (const t of themes) {
      const precision = t.precision !== undefined && t.precision !== null
        ? `${decFmt(t.precision * 100, 0)}%`
        : '–';
      const range = t.precision_lo !== undefined && t.precision_lo !== null
        ? `${decFmt(t.precision_lo * 100, 0)}% to ${decFmt(t.precision_hi * 100, 0)}%`
        : '–';
      const n = t.precision_n !== undefined && t.precision_n !== null ? intFmt(t.precision_n) : '–';
      rows += `<tr><td>${t.label}</td><td class="num">${precision}</td><td class="num">${range}</td><td class="num">${n}</td></tr>`;
    }
  }
  if (portfolio.weak_themes && portfolio.weak_themes.length) {
    rows += `<tr><td colspan="4" style="color:var(--muted)">Not shown (precision under 0.7): ${portfolio.weak_themes.join(', ')}</td></tr>`;
  }
  return rows;
}

export async function render(container) {
  container.innerHTML = '<div class="empty-state">Loading method…</div>';
  let portfolio;
  try {
    portfolio = await loadPortfolio();
  } catch (err) {
    container.innerHTML = `<div class="error-state">Could not load method data. ${err.message}</div>`;
    return;
  }

  const totalReviews = Object.values(portfolio.stats.reviews).reduce((s, r) => s + r.reviews, 0);
  const m = portfolio.matcher;
  const ea = portfolio.event_appendix;

  container.innerHTML = `
    <div class="method-intro">
      <h1>Every number rests on reviews, listings matched into products, and a keyword-tagged complaint</h1>
      <p>Where the numbers come from, how they are cleaned and joined, how complaints are tagged, and what the tool cannot tell you.</p>
    </div>

    <section class="method-section">
      <h2>1. What this tool answers</h2>
      <div class="method-body">
        <p>Pick a Shark or Ninja product and see what its owners report after buying it: what they complain about, when they say it stopped working, how ratings change over the product's life, and how refurbished units compare with new. Every number is a share of written reviews, compared with SharkNinja's own average for that product type and with five peer brands: Bissell, Dyson, iRobot, Keurig and Instant Pot.</p>
        <p>Complaint shares are shares of 1 and 2-star reviews, never failure rates: they say how often a theme shows up among the negative reviews a product received, not what fraction of units failed.</p>
      </div>
    </section>

    <section class="method-section">
      <h2>2. The data</h2>
      <div class="method-body">
        <p>Amazon Reviews 2023, published by the McAuley Lab at UC San Diego: product listings and every written review, from 1996 to September 2023. It was filtered from 3.8 million Home &amp; Kitchen and Appliances listings down to those sold under the Shark and Ninja stores, plus Amazon Renewed listings of their products, and the five peer brands.</p>
        <table>
          <tbody>
            <tr><td>SharkNinja listings kept, including ${intFmt(portfolio.stats.listings_bundles)} bundles</td><td class="mono num">${intFmt(portfolio.stats.listings_in_scope)}</td></tr>
            <tr><td>SharkNinja products after matching</td><td class="mono num">${intFmt(portfolio.stats.products)}</td></tr>
            <tr><td>Unit reviews analysed, SharkNinja and peers</td><td class="mono num">${intFmt(totalReviews)}</td></tr>
            <tr><td>Data complete through</td><td class="mono num">${portfolio.complete_through}</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="method-section">
      <h2>3. Peer brands</h2>
      <div class="method-body">
        <p>Five brands: Bissell, Dyson, iRobot, Keurig and Instant Pot. Peers are matched by store name, the same way SharkNinja is: only listings sold under the brand's own Amazon store are kept, so third-party resellers and unrelated products with a similar name are excluded. Peer listings go through the same cleaning rules (product type, accessories, refurbished titles) but are not joined into products, so each peer listing counts as one unit. Peer listings of kinds SharkNinja does not sell, such as carpet shampooers, handheld steam cleaners and robot mops, are left out, and peer irons and sweepers are not compared because the matching listings turned out to be different products. A peer brand counts for a type only with at least 200 reviews in it. Not every peer brand competes in every product type; the type table on the Overview page names which peer brands are counted for each type.</p>
      </div>
    </section>

    <section class="method-section">
      <h2>4. Cleaning</h2>
      <div class="method-body">
        <p>Every rule is deterministic and records how many rows it changed. Nothing is deleted; unusual rows are flagged instead.</p>
        <ul>
          <li><strong>Model number</strong> comes from the listing's model field, or from the title when the field is missing or contradicts a model named in the title. Listing IDs placed in the model field are rejected.</li>
          <li><strong>Accessories</strong> are told apart from full units by where part words (filter, lid, hose) sit relative to product words (vacuum, blender). Model numbers in a part's title, such as "for NV500, NV501", are kept as compatible models, never as the part's identity.</li>
          <li><strong>Other brands</strong> that share a store name are marked unrelated and left out.</li>
          <li><strong>Product type</strong> comes from Amazon's category path first and the title second.</li>
        </ul>
      </div>
    </section>

    <section class="method-section">
      <h2>5. Matching listings into products</h2>
      <div class="method-body">
        <p>Amazon often sells one product under several listings: colours, retailer-exclusive codes, refurbished units, bundles. They are joined into one product in three passes. First, listings sharing a core model (the letters and digits, so WS642BL and WS642GN are one product) are grouped. Second, listings without a model number are scored against known products of the same brand and type, on title overlap, model codes in the title, price and conflicting numbers. Third, what is left is clustered, and anything still unmatched keeps its own ID rather than being forced into a match.</p>
        <table>
          <tbody>
            <tr><td>Public benchmark (Walmart vs Amazon listings), held-out test</td><td class="mono num">F1 ${decFmt(m.benchmark_f1, 3)}</td></tr>
            <tr><td>SharkNinja held-out pairs, labelled blind</td><td class="mono num">precision ${decFmt(m.sn_precision, 3)} &middot; recall ${decFmt(m.sn_recall, 3)}</td></tr>
            <tr><td>After adjudicating disputed labels</td><td class="mono num">precision ${decFmt(m.sn_precision_adjudicated, 3)} &middot; recall ${decFmt(m.sn_recall_adjudicated, 3)}</td></tr>
          </tbody>
        </table>
        <p style="color:var(--muted)">Precision: of the pairs the matcher joined, the share that truly are the same product. Recall: of the pairs that truly are the same product, the share the matcher found.</p>
      </div>
    </section>

    <section class="method-section">
      <h2>6. The monthly timeline and product age</h2>
      <div class="method-body">
        <p>Each product gets a month-by-month series of review count and average rating, one for new units and one for refurbished units, with months that had no reviews shown as zero rather than left out. A product's launch date is its earliest evidence: the listing's first-available date or its first review, whichever came first. A product's age at each review is measured from that launch date and grouped into bands (0 to 6 months, 7 to 12 months, year 2, years 3 to 4, year 5 and later) for the life cycle chart.</p>
        <p><strong>Data is complete through March 2023.</strong> SharkNinja review volume runs at about 3,000 to 4,100 a month during 2022, then falls sharply in the following months, because of when the source was collected. Those months are shaded on charts and never read as owners suddenly going quiet.</p>
      </div>
    </section>

    <section class="method-section">
      <h2>7. Complaint themes</h2>
      <div class="method-body">
        <p>A rules-based keyword tagger scans each 1 or 2-star review's title and text for phrases tied to a specific complaint, such as "stopped working", "leaks" or "missing parts". A review can match more than one theme. Each theme's precision, how often a match is a genuine instance of that complaint, was measured by hand-labelling a sample of matches; themes under 0.7 precision are not shown anywhere in this tool.</p>
        <table>
          <thead><tr><th>Theme</th><th class="num">Precision</th><th class="num">Range</th><th class="num">Sample</th></tr></thead>
          <tbody>${themeRows(portfolio)}</tbody>
        </table>
      </div>
    </section>

    <section class="method-section">
      <h2>8. Stated time to failure</h2>
      <div class="method-body">
        <p>Reviews that report a product failing and name a time, such as "after 6 months" or "died at a year", are parsed into a number of months and grouped into bands: under a month, 1 to 3 months, 4 to 11 months, about a year, and 2 years or more. Owners tend to round to familiar numbers (6, 12, 24 months), which is visible as spikes at those exact values; only reviews that state a time are counted, so this is not a survival curve over every unit sold.</p>
      </div>
    </section>

    <section class="method-section">
      <h2>9. What this does not claim</h2>
      <div class="method-body">
        <ul>
          <li>Complaint shares are shares of 1 and 2-star reviews, never failure rates: they say nothing about what fraction of all units sold ever failed.</li>
          <li>Written reviews are self-selected. Owners who write reviews are not a random sample of owners, and are more likely to write after a bad experience or a long time of use.</li>
          <li>Keyword themes are not verified failures; a review can be tagged by a theme's keywords without describing a genuine defect, at the rate the theme's measured precision states.</li>
          <li>This tool makes no demand, sales or causal claims. It does not know why a complaint rose in a given year, only that it did.</li>
        </ul>
      </div>
    </section>

    <section class="method-section">
      <h2>10. Appendix: what we tested and could not detect</h2>
      <div class="method-body">
        <p>An earlier version of this tool tested whether specific events, a sibling model launching, refurbished units appearing, or a run of low ratings, moved a product's review volume. Across ${intFmt(ea.events)} candidate events, ${intFmt(ea.testable)} had enough data to test. A placebo test run on fake event dates found the method would call a false alarm about ${decFmt(ea.placebo_false_alarm * 100, 1)}% of the time before correction; after a false-discovery check across every event tested at once, ${ea.survive_fdr} survived. Pooled averages existed but are consistent with selection (launches and refurbished units tend to follow growth that was already happening), so they are not shown as effects anywhere in this tool.</p>
        <p>Review volume does track the Amazon Best Sellers Rank snapshot across products (Spearman &minus;0.71, n = 431) but has not been validated as a demand signal over time, which is why this tool makes no demand claims and instead reports what owners say, not how many units sold.</p>
      </div>
    </section>

    <section class="method-section">
      <h2>11. Terms</h2>
      <div class="method-body">
        <dl>
          <dt>Listing</dt><dd>One Amazon product page, with its own ID.</dd>
          <dt>Product</dt><dd>One physical unit model; it may have several listings.</dd>
          <dt>Family</dt><dd>Products sharing a model prefix, such as AF (air fryers) or NV (Navigator vacuums).</dd>
          <dt>Refurbished</dt><dd>Units sold through Amazon Renewed.</dd>
          <dt>Peers</dt><dd>Bissell, Dyson, iRobot, Keurig and Instant Pot units sold in their own Amazon stores, cleaned with the same rules as SharkNinja and compared within the same product type.</dd>
        </dl>
      </div>
    </section>

    <section class="method-section">
      <h2>12. Sources</h2>
      <div class="method-body">
        <p>Amazon Reviews 2023, McAuley Lab, UC San Diego. Matching benchmarks: Walmart-Amazon, Abt-Buy and Amazon-Google from the UW&ndash;Madison Magellan collection. Catalogue cross-check: ManualsLib's index of Shark vacuum manuals.</p>
      </div>
    </section>
  `;
}
