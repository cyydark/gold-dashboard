/**
 * Time formatting utilities shared by chart plugins.
 */

const pad = (n) => String(n).padStart(2, "0");

/**
 * Format Unix timestamp (ms) as "北京 M月d日 HH:mm".
 * @param {number} ts - Unix timestamp in milliseconds
 * @returns {string}
 */
export function fmtBJ(ts) {
  const d = new Date(ts);
  return `${pad(d.getMonth() + 1)}月${pad(d.getDate())}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Format Unix timestamp (ms) as "美东 M月d日 HH:mm" (UTC-12, approximate ET).
 * @param {number} ts - Unix timestamp in milliseconds
 * @returns {string}
 */
export function fmtUS(ts) {
  const d = new Date(ts - 12 * 3600 * 1000);
  return `${pad(d.getMonth() + 1)}月${pad(d.getDate())}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Binary search: nearest data point to targetTs in O(log n).
 * Skips null points (y === null) so gap midpoints are never returned.
 * @param {Array<{x: Date, y: number}>} data
 * @param {number} targetTs - Unix timestamp in ms
 * @returns {{x: Date, y: number} | null}
 */
export function findNearest(data, targetTs) {
  if (!data || !data.length) return null;
  let lo = 0, hi = data.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (data[mid].x < targetTs) lo = mid + 1;
    else hi = mid;
  }

  const valid = (pt) => pt && pt.y !== null && pt.y !== undefined;

  let best = valid(data[lo]) ? data[lo] : null;
  let bestDiff = best ? Math.abs(best.x - targetTs) : Infinity;
  if (lo > 0 && valid(data[lo - 1])) {
    const diff = Math.abs(data[lo - 1].x - targetTs);
    if (diff < bestDiff) { bestDiff = diff; best = data[lo - 1]; }
  }
  if (lo < data.length - 1 && valid(data[lo + 1])) {
    const diff = Math.abs(data[lo + 1].x - targetTs);
    if (diff < bestDiff) best = data[lo + 1];
  }
  return best;
}
