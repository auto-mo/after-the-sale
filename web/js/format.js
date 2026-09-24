const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH_NAMES_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** "2019-08" -> "Aug 2019" */
export function monthShort(m) {
  if (!m) return '';
  const [y, mo] = m.split('-');
  return `${MONTH_NAMES[Number(mo) - 1]} ${y}`;
}

/** "2019-08" -> "August 2019" */
export function monthLong(m) {
  if (!m) return '';
  const [y, mo] = m.split('-');
  return `${MONTH_NAMES_LONG[Number(mo) - 1]} ${y}`;
}

/** "2018-08-13" -> "13 Aug 2018" */
export function dateShort(d) {
  if (!d) return '';
  const [y, mo, day] = d.split('-');
  return `${Number(day)} ${MONTH_NAMES[Number(mo) - 1]} ${y}`;
}

// A single em dash never appears in rendered copy (house style); this en
// dash stands in for "no value" in tables and stat tiles.
export const EMPTY = '–';
const MINUS = '−';

export function intFmt(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return EMPTY;
  return Math.round(n).toLocaleString('en-US');
}

export function decFmt(n, digits = 1) {
  if (n === null || n === undefined || Number.isNaN(n)) return EMPTY;
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** Percentage with a true minus sign for negatives (not the hyphen-minus). */
export function pctFmt(n, digits = 1) {
  if (n === null || n === undefined || Number.isNaN(n)) return EMPTY;
  const sign = n > 0 ? '+' : n < 0 ? MINUS : '';
  return `${sign}${decFmt(Math.abs(n), digits)}%`;
}

export function rangeFmt(lo, hi, digits = 1) {
  if (lo === null || lo === undefined || hi === null || hi === undefined) return '';
  return `${pctFmt(lo, digits)} to ${pctFmt(hi, digits)}`;
}

const LAUNCH_SOURCE_LABEL = {
  date_first_available: 'listed first-available date',
  'first review (proxy)': 'first review',
  'first review (earlier than listed date)': 'first review, earlier than the listed date',
  'first renewed review (proxy)': 'first refurbished review',
};

export function humanizeLaunchSource(src) {
  return LAUNCH_SOURCE_LABEL[src] || src || '';
}

const TYPE_LABEL = {
  'accessory/part': 'accessory or part',
  'floor-care consumable': 'floor-care consumable',
  unclassified: 'unclassified',
  'iron/steamer': 'iron or steamer',
};

/** "vacuum-upright/canister" -> "upright/canister vacuum"; other types pass
 * through a small override table, or are returned unchanged. */
export function humanizeType(type) {
  if (!type) return '';
  if (type.startsWith('vacuum-')) {
    const rest = type.slice('vacuum-'.length).replace(/-/g, ' ').replace('/', ' or ');
    return rest === 'other' ? 'vacuum' : `${rest} vacuum`;
  }
  return TYPE_LABEL[type] || type;
}

/** Escape text for safe insertion as textContent already handles this, but
 * kept for the rare case we build innerHTML from user-controlled strings. */
export function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

export function monthIndex(m) {
  const [y, mo] = m.split('-').map(Number);
  return y * 12 + (mo - 1);
}

export function addMonths(m, delta) {
  const idx = monthIndex(m) + delta;
  const y = Math.floor(idx / 12);
  const mo = (idx % 12) + 1;
  return `${y}-${String(mo).padStart(2, '0')}`;
}
