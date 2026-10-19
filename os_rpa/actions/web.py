import os
from typing import Any, Callable, Dict, Optional, Tuple
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
from os_rpa.actions.base import BaseAction
from os_rpa.engine.context import ExecutionContext


def launch_with_fallback(launch: Callable[..., Any], channel: str, **kwargs) -> Tuple[Any, str]:
    """Launch Chromium via a Playwright launcher (`chromium.launch` or `launch_persistent_context`).
    channel: 'auto' (bundled, falling back to installed Edge), 'chromium' (bundled only), or an
    installed browser channel like 'msedge'/'chrome'. Returns (browser_or_context, browser_name)."""
    channel = channel or "auto"
    if channel not in ("auto", "chromium"):
        return launch(channel=channel, **kwargs), channel
    try:
        return launch(**kwargs), "chromium"
    except Exception as e:
        # Bundled browser not downloaded (e.g. `playwright install` blocked by a proxy)
        if channel == "chromium" or "Executable doesn't exist" not in str(e):
            raise
        return launch(channel="msedge", **kwargs), "msedge"


class PlaywrightSession:
    """Singleton session keeping active browser/page open between workflow steps."""
    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    _page: Optional[Page] = None
    browser_name: Optional[str] = None
    debug_port: Optional[int] = None

    @classmethod
    def _launch(cls, headless: bool, channel: str) -> Browser:
        from os_rpa.inspector import browsers

        chromium = cls._playwright.chromium
        # Headed runs need the full bundled browser; skip a slow failing launch when it isn't downloaded
        if channel == "auto" and not headless and not Path(chromium.executable_path).exists():
            channel = "msedge"
        args = []
        cls.debug_port = None
        # Visible browsers get a localhost debug port so the Studio inspector can attach to them
        if not headless and browsers.inspectable_browsers_enabled():
            cls.debug_port = browsers.free_port()
            args = [f"--remote-debugging-port={cls.debug_port}", "--remote-debugging-address=127.0.0.1"]
        browser, cls.browser_name = launch_with_fallback(chromium.launch, channel, headless=headless, args=args)
        if cls.debug_port:
            browsers.register(cls.debug_port, cls.browser_name)
        return browser

    @classmethod
    def get_or_create_page(cls, headless: bool = True, channel: Optional[str] = None) -> Page:
        if cls._page and not cls._page.is_closed():
            return cls._page

        if not cls._playwright:
            cls._playwright = sync_playwright().start()

        if not cls._browser or not cls._browser.is_connected():
            channel = channel or os.environ.get("OS_RPA_BROWSER_CHANNEL", "auto")
            cls._browser = cls._launch(headless, channel)
            cls._context = cls._browser.new_context()

        cls._page = cls._context.new_page()
        return cls._page

    @classmethod
    def close(cls):
        try:
            if cls._page and not cls._page.is_closed():
                cls._page.close()
            if cls._context:
                cls._context.close()
            if cls._browser and cls._browser.is_connected():
                cls._browser.close()
            if cls._playwright:
                cls._playwright.stop()
        except Exception:
            pass
        finally:
            from os_rpa.inspector import browsers

            browsers.unregister(cls.debug_port)
            cls.debug_port = None
            cls._page = None
            cls._context = None
            cls._browser = None
            cls._playwright = None


class WebOpenBrowserAction(BaseAction):
    name = "web.open_browser"
    category = "web"
    description = "Opens a Chromium browser session and navigates to the initial URL."
    params_schema = {
        "url": {"type": "string", "label": "Initial URL", "default": "https://google.com"},
        "headless": {"type": "boolean", "label": "Headless mode", "default": True},
        "channel": {
            "type": "select",
            "options": ["auto", "chromium", "msedge", "chrome"],
            "label": "Browser",
            "default": "auto",
        },
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        url = params.get("url", "https://google.com")
        headless = bool(params.get("headless", True))

        page = PlaywrightSession.get_or_create_page(headless=headless, channel=params.get("channel"))
        page.goto(url, wait_until="domcontentloaded")
        title = page.title()
        context.success(f"Opened {PlaywrightSession.browser_name} at {url} (Title: '{title}')")
        return {"url": url, "title": title}


class WebNavigateAction(BaseAction):
    name = "web.navigate"
    category = "web"
    description = "Navigates the currently open browser to a new URL."
    params_schema = {
        "url": {"type": "string", "label": "Target URL", "required": True},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        url = params.get("url")
        if not url:
            raise ValueError("URL is required")

        page = PlaywrightSession.get_or_create_page()
        page.goto(url, wait_until="domcontentloaded")
        context.success(f"Navigated to {url}")
        return page.url


class WebClickAction(BaseAction):
    name = "web.click"
    category = "web"
    description = "Clicks a web element matching the CSS or XPath selector."
    params_schema = {
        "selector": {"type": "string", "label": "Selector (CSS or XPath)", "required": True},
        "timeout_ms": {"type": "number", "label": "Timeout (ms)", "default": 5000},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        selector = params.get("selector")
        timeout_ms = int(params.get("timeout_ms", 5000))

        page = PlaywrightSession.get_or_create_page()
        page.wait_for_selector(selector, timeout=timeout_ms)
        page.click(selector, timeout=timeout_ms)
        context.success(f"Clicked element '{selector}'")
        return True


class WebTypeAction(BaseAction):
    name = "web.type"
    category = "web"
    description = "Fills or types text into a web input field."
    params_schema = {
        "selector": {"type": "string", "label": "Input Selector", "required": True},
        "text": {"type": "string", "label": "Text to Type", "required": True},
        "clear_first": {"type": "boolean", "label": "Clear before typing", "default": True},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        selector = params.get("selector")
        text = str(params.get("text", ""))
        clear_first = bool(params.get("clear_first", True))

        page = PlaywrightSession.get_or_create_page()
        if clear_first:
            page.fill(selector, text)
        else:
            page.type(selector, text)
        context.success(f"Typed text into '{selector}'")
        return text


class WebGetTextAction(BaseAction):
    name = "web.get_text"
    category = "web"
    description = "Extracts text content or attribute from a web element."
    params_schema = {
        "selector": {"type": "string", "label": "Element Selector", "required": True},
        "attribute": {"type": "string", "label": "Attribute name (blank for inner text)", "default": ""},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        selector = params.get("selector")
        attribute = params.get("attribute")

        page = PlaywrightSession.get_or_create_page()
        el = page.wait_for_selector(selector, timeout=5000)
        if attribute:
            val = el.get_attribute(attribute)
        else:
            val = el.inner_text()

        context.success(f"Extracted text from '{selector}': '{val}'")
        return val


class WebScreenshotAction(BaseAction):
    name = "web.screenshot"
    category = "web"
    description = "Captures a screenshot of the current page."
    params_schema = {
        "output_path": {"type": "string", "label": "Save Path", "default": "data/screenshot.png"},
    }

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        output_path = Path(params.get("output_path", "data/screenshot.png"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        page = PlaywrightSession.get_or_create_page()
        page.screenshot(path=str(output_path))
        context.success(f"Saved screenshot to {output_path}")
        return str(output_path)


class WebCloseBrowserAction(BaseAction):
    name = "web.close_browser"
    category = "web"
    description = "Closes the current browser and releases resources."
    params_schema = {}

    def execute(self, params: Dict[str, Any], context: ExecutionContext) -> Any:
        PlaywrightSession.close()
        context.success("Closed browser session")
        return True

