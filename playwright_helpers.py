from playwright.sync_api import sync_playwright, Page, Browser
from typing import Dict, List, Optional
import time


class BrowserContext:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._pw = None
        self.browser: Optional[Browser] = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=self.headless)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.browser:
            self.browser.close()
        if self._pw:
            self._pw.stop()

    def new_page(self) -> Page:
        assert self.browser, "Browser not started"
        ctx = self.browser.new_context()
        return ctx.new_page()


def load_jlpt_page(page: Page, level: int):
    """Load the JLPT list page for a given level (1..5).
    The site uses hash routing; include fragment in URL.
    """
    url = f"https://ja.dict.naver.com/#/jlpt/list?level={level}"
    page.goto(url, wait_until='domcontentloaded')
    # wait for renderer to populate list; basic wait
    time.sleep(1.0)


def discover_pos_buttons(page: Page) -> Dict[str, str]:
    """Return a map of pos_label -> selector/value. We try to find POS buttons in the JLPT page UI.
    The returned key should be a normalized label like 'noun', 'verb', 'adj'.
    """
    # common container candidates
    candidates = [
        "div.jlpt_filter",
        "div.filter",
        "div.filter_area",
        "div[class*='filter']",
    ]
    for sel in candidates:
        try:
            container = page.query_selector(sel)
            if container:
                buttons = container.query_selector_all('button')
                if buttons:
                    result = {}
                    for b in buttons:
                        txt = (b.inner_text() or '').strip()
                        if not txt:
                            continue
                        key = txt.lower()
                        result[key] = None
                    return result
        except Exception:
            continue
    # fallback: search for any button sets
    btns = page.query_selector_all('button')
    res = {}
    for b in btns:
        txt = (b.inner_text() or '').strip()
        if txt and len(txt) < 30:
            res[txt.lower()] = None
    return res


def click_pos_button(page: Page, pos_label: str) -> bool:
    """Try clicking a POS button by matching its text content (case-insensitive).
    Returns True if a click was performed.
    """
    buttons = page.query_selector_all('button')
    target = pos_label.strip().lower()
    for b in buttons:
        txt = (b.inner_text() or '').strip().lower()
        if txt == target or txt.startswith(target):
            b.click()
            time.sleep(0.8)
            return True
    return False


def wait_for_list(page: Page, timeout: float = 5.0) -> bool:
    """Wait until list items appear on the page."""
    end = time.time() + timeout
    while time.time() < end:
        # try a few selectors
        for sel in ["ul.list > li", "ul.word_list > li", "div.list li", "div.result_list li"]:
            items = page.query_selector_all(sel)
            if items and len(items) > 0:
                return True
        time.sleep(0.3)
    return False
