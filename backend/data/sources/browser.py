"""BrowserManager: 统一管理 Playwright Chromium 生命周期（单例，线程安全）."""
import logging
import threading
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class BrowserManager:
    """线程安全的 Chromium 单例管理器。"""
    _instance: "BrowserManager | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "BrowserManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._browser = None
        self._playwright = None
        self._initialized = True

    def launch(self) -> None:
        """启动 persistent Chromium（幂等，重复调用无害）。"""
        with self._lock:
            if self._browser is not None:
                return
            try:
                self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.launch(
                    executable_path=CHROME_PATH,
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"],
                )
                logger.info("BrowserManager: Chromium launched")
            except Exception as e:
                logger.warning(f"BrowserManager: launch failed: {e}")
                self._browser = None

    def close(self) -> None:
        """关闭 Chromium（幂等）。"""
        with self._lock:
            if self._browser is not None:
                try:
                    self._browser.close()
                    self._browser = None
                except Exception as e:
                    logger.warning(f"BrowserManager: close error: {e}")
            if self._playwright is not None:
                try:
                    self._playwright.stop()
                    self._playwright = None
                except Exception as e:
                    logger.warning(f"BrowserManager: playwright stop error: {e}")
            logger.info("BrowserManager: Chromium closed")

    @property
    def browser(self):
        """返回 browser 实例，若未启动则 lazy launch。"""
        with self._lock:
            if self._browser is None:
                self.launch()
            return self._browser

    def get_new_context(self):
        """每次调用创建新 context（隔离）。"""
        return self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
