/**
 * SSE client - connects to /stream and dispatches price updates.
 * Calls window.onPriceUpdate(prices) on each update.
 */
class SSEClient {
  constructor() {
    this.source = null;
    this._retryDelay = 5000;
    this._connect();
  }

  _connect() {
    if (this.source) {
      this.source.close();
    }
    this.source = new EventSource("/stream");

    this.source.onmessage = (event) => {
      try {
        const prices = JSON.parse(event.data);
        if (typeof window.onPriceUpdate === "function") {
          window.onPriceUpdate(prices);
        }
      } catch (e) {
        // silently ignore malformed SSE data
      }
    };

    this.source.onerror = () => {
      this.source.close();
      const delay = this._retryDelay;
      this._retryDelay = Math.min(this._retryDelay * 1.5, 60000);
      setTimeout(() => this._connect(), delay);
    };
  }
}

window.sseClient = new SSEClient();
