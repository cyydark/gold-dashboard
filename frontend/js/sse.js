/**
 * SSE client - connects to /stream and dispatches price updates.
 * Calls window.onPriceUpdate(prices) on each update.
 */
class SSEClient {
  constructor() {
    this.source = null;
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
        console.warn("SSE parse error:", e);
      }
    };

    this.source.onerror = () => {
      // Reconnect after 5s
      this.source.close();
      setTimeout(() => this._connect(), 5000);
    };
  }
}

window.sseClient = new SSEClient();
