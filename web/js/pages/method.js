export async function render(container) {
  container.innerHTML = `
    <div class="method-intro">
      <h1>Every verdict rests on reviews, listings matched into products, and a comparison group</h1>
      <p>Where the numbers come from, how they are cleaned and joined, how a verdict is reached, and what the tool cannot tell you.</p>
    </div>

    <section class="method-section">
      <h2>1. What this tool answers</h2>
      <div class="method-body">
        <p>Pick a Shark or Ninja product and see what moved its demand on Amazon, and what did not. Three kinds of event are tested: a sibling model launching in the same family, refurbished units of the product appearing, and a run of low-rating months.</p>
        <p>Demand is measured through written reviews per month, split into reviews of new units and of refurbished units. Every event gets one of three verdicts: <strong>Moved</strong>, <strong>No clear change</strong> or <strong>Not enough data</strong>, shown with the size of the change and its range.</p>
      </div>
    </section>

    <section class="method-section">
      <h2>2. The data</h2>
      <div class="method-body">
        <p>Amazon Reviews 2023, published by the McAuley Lab at UC San Diego: product listings and every written review, from 1996 to September 2023. It was filtered from 3.8 million Home &amp; Kitchen and Appliances listings down to those sold under the Shark and Ninja stores, plus Amazon Renewed listings of their products.</p>
        <table>
          <tbody>
            <tr><td>Listings kept</td><td class="mono num">2,012</td></tr>
            <tr><td>Sold by the Shark or Ninja store</td><td class="mono num">1,169</td></tr>
            <tr><td>Amazon Renewed (refurbished) listings</td><td class="mono num">843</td></tr>
            <tr><td>Reviews kept after removing exact duplicates</td><td class="mono num">290,614</td></tr>
            <tr><td>Exact duplicates set aside, with the reason</td><td class="mono num">2,656</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="method-section">
      <h2>3. Cleaning</h2>
      <div class="method-body">
        <p>Every rule is deterministic and records how many rows it changed. Nothing is deleted; unusual rows are flagged instead.</p>
        <ul>
          <li><strong>Model number</strong> comes from the listing's model field, or from the title when the field is missing or contradicts a model named in the title. Listing IDs placed in the model field are rejected.</li>
          <li><strong>Accessories</strong> are told apart from full units by where part words (filter, lid, hose) sit relative to product words (vacuum, blender). Model numbers in a part's title, such as "for NV500, NV501", are kept as compatible models, never as the part's identity.</li>
          <li><strong>Other brands</strong> that share the store name (Sharkk, Shark Skinz, NINJA Brand rug pads) are marked unrelated and left out: 18 listings.</li>
          <li><strong>Product type</strong> comes from Amazon's category path first and the title second.</li>
        </ul>
      </div>
    </section>

    <section class="method-section">
      <h2>4. Matching listings into products</h2>
      <div class="method-body">
        <p>Amazon often sells one product under several listings: colours, retailer-exclusive codes, refurbished units, bundles. They are joined into one product in three passes. First, listings sharing a core model (the letters and digits, so WS642BL and WS642GN are one product) are grouped. Second, listings without a model number are scored against known products of the same brand and type, on title overlap, model codes in the title, price and conflicting numbers. Third, what is left is clustered, and anything still unmatched keeps its own ID rather than being forced into a match. A short alias list, with the evidence recorded, covers cases where the digits differ but the unit is the same (AF100 and AF101).</p>
        <table>
          <tbody>
            <tr><td>Listings in scope &rarr; products</td><td class="mono num">1,967 &rarr; 1,138</td></tr>
            <tr><td>Public benchmark (Walmart vs Amazon listings), held-out test</td><td class="mono num">F1 0.852</td></tr>
            <tr><td>SharkNinja held-out pairs, labelled blind</td><td class="mono num">precision 0.869 &middot; recall 0.914</td></tr>
            <tr><td>After settling 5 disputed labels from listing data</td><td class="mono num">precision 0.948 &middot; recall 0.917</td></tr>
          </tbody>
        </table>
        <p style="color:var(--muted)">Precision: of the pairs the matcher joined, the share that truly are the same product. Recall: of the pairs that truly are the same product, the share the matcher found.</p>
      </div>
    </section>

    <section class="method-section">
      <h2>5. The monthly timeline</h2>
      <div class="method-body">
        <p>Each product gets a month-by-month series of review count and average rating, one for new units and one for refurbished units, with months that had no reviews shown as zero rather than left out. Reviews dated before a listing's launch are kept at product level, because they were carried over from an earlier listing of the same product. A product's launch date is its earliest evidence: the listing's first-available date or its first review, whichever came first.</p>
        <p><strong>Data is complete through March 2023.</strong> Review volume holds at 3,000 to 4,100 a month through 2022, then falls to 2,007 in April 2023 and 418 in August, because of when the source was collected. Those months are shaded and never read as a real decline.</p>
      </div>
    </section>

    <section class="method-section">
      <h2>6. How a verdict is reached</h2>
      <div class="method-body">
        <p>For each event, the product's reviews in the months before and after are compared with a comparison group of up to 10 similar products: same product type, a different family, a similar life stage and prior review volume, and no such event of their own in that window. Comparisons built on a looser match (fewer close products available) are flagged with their tier. The comparison group absorbs market-wide swings such as seasonality or spring 2020, so the verdict rests on the difference between the product and its comparison group, not on the product's raw before-and-after change.</p>
        <p>The change itself is the difference in log change of monthly reviews before versus after: a 12-month window on each side for sibling launches and refurbished-unit events, a 3-month window for low-rating runs. Its range comes from resampling the comparison group plus the natural month-to-month swing products show even with no event, measured by testing the same method on fake event dates.</p>
        <p><strong>Moved</strong> when the change is at least 15% in either direction, its range excludes zero, <em>and</em> it survives a false-discovery check run across every event tested at once (a single large-looking change is not enough by itself). <strong>No clear change</strong> when the change does not clear that bar. <strong>Not enough data</strong> when the product had fewer than 30 reviews before the event, or fewer than 3 comparable products could be found.</p>
        <p>A fake-date test makes the false-discovery step necessary: run on 3,868 events with no real event behind them, the method without that step would still call about 1 in 10 "Moved" purely from normal month-to-month noise.</p>
      </div>
    </section>

    <section class="method-section">
      <h2>7. What this does not claim</h2>
      <div class="method-body">
        <ul>
          <li>Review volume stands in for demand. Written reviews are a fraction of star ratings (AF101: about 5,900 reviews against 45,929 ratings).</li>
          <li>A verdict describes what happened alongside an event compared with similar products; it cannot prove the event caused it.</li>
          <li>A single event's "Moved" verdict already accounts for chance across every event tested; even so, treat one event as a single data point. The pooled averages on the Findings page are the more reliable level to read.</li>
          <li>There is no price, stock, sales-rank or seller history in the data, so price changes, stock-outs, rank and buy box are out of scope.</li>
          <li>Some listings have no model number and a generic title; they stay separate products, which makes the product count slightly high (likely 1,100 to 1,130 rather than 1,138).</li>
        </ul>
      </div>
    </section>

    <section class="method-section">
      <h2>8. Terms</h2>
      <div class="method-body">
        <dl>
          <dt>Listing</dt><dd>One Amazon product page, with its own ID.</dd>
          <dt>Product</dt><dd>One physical unit model; it may have several listings.</dd>
          <dt>Family</dt><dd>Products sharing a model prefix, such as AF (air fryers) or NV (Navigator vacuums).</dd>
          <dt>Refurbished</dt><dd>Units sold through Amazon Renewed.</dd>
          <dt>Comparison group</dt><dd>Similar products without the event, used as the baseline.</dd>
        </dl>
      </div>
    </section>

    <section class="method-section">
      <h2>9. Sources</h2>
      <div class="method-body">
        <p>Amazon Reviews 2023, McAuley Lab, UC San Diego. Matching benchmarks: Walmart-Amazon, Abt-Buy and Amazon-Google from the UW&ndash;Madison Magellan collection. Catalogue cross-check: ManualsLib's index of Shark vacuum manuals.</p>
      </div>
    </section>
  `;
}
