/**
 * Simple event bus — replaces PollingManager callback hell.
 * Components publish events and subscribe to them.
 */
const _handlers = new Map();

export const EventBus = {
  /**
   * Subscribe to an event.
   * @param {string} event - event name
   * @param {Function} handler - called with the event data
   * @returns {Function} unsubscribe function
   */
  on(event, handler) {
    if (!_handlers.has(event)) _handlers.set(event, new Set());
    _handlers.get(event).add(handler);
    return () => this.off(event, handler);
  },

  /**
   * Unsubscribe a specific handler.
   */
  off(event, handler) {
    if (_handlers.has(event)) _handlers.get(event).delete(handler);
  },

  /**
   * Publish an event — all handlers are called with `data`.
   */
  emit(event, data) {
    if (_handlers.has(event)) {
      for (const handler of _handlers.get(event)) {
        try { handler(data); } catch (e) { console.error(`[EventBus] ${event} handler error:`, e); }
      }
    }
  },

  /**
   * Remove all handlers for an event (or all events).
   */
  clear(event) {
    if (event) { _handlers.delete(event); }
    else { _handlers.clear(); }
  },
};

// Convenience aliases
export const on  = (event, handler) => EventBus.on(event, handler);
export const off = (event, handler) => EventBus.off(event, handler);
export const emit = (event, data)   => EventBus.emit(event, data);
