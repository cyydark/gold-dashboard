/**
 * Shared utility functions.
 */

/**
 * Escape HTML special characters to prevent XSS.
 * @param {string} s
 * @returns {string}
 */
export function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
