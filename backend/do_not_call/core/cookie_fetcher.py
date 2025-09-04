import asyncio
from typing import Dict, Optional
from loguru import logger

from playwright.async_api import async_playwright


FREEDNCLIST_URL = "https://freednclist.com/"


async def fetch_freednclist_cookies() -> Dict[str, str]:
    """Use Playwright to open freednclist.com and return cookies as a dict."""
    logger.info("Fetching FreeDNCList cookies via Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(FREEDNCLIST_URL, wait_until="domcontentloaded")

        # Give the site a brief moment to set cookies
        await page.wait_for_timeout(1000)

        cookies = await context.cookies()
        await browser.close()

        cookie_map: Dict[str, str] = {}
        for c in cookies:
            name = c.get("name")
            value = c.get("value")
            if name and value:
                cookie_map[name] = value

        logger.info(f"Retrieved cookies: {list(cookie_map.keys())}")
        return cookie_map


async def fetch_freednclist_phpsessid() -> Optional[str]:
    """Fetch PHPSESSID from freednclist.com, if present."""
    cookies = await fetch_freednclist_cookies()
    return cookies.get("PHPSESSID")


def fetch_freednclist_phpsessid_sync() -> Optional[str]:
    """Synchronous helper to fetch PHPSESSID (for non-async callers)."""
    return asyncio.run(fetch_freednclist_phpsessid())


