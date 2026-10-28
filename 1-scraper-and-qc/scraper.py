"""
scraper.py — Playwright Scraper Engine (UPDATED)
"""

import asyncio
from typing import Any, Callable, Awaitable, Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from logger import get_logger
import settings

log = get_logger(__name__, log_file=settings.LOG_FILE)


class Scraper:
    def __init__(
        self,
        headless: bool = None,
        timeout: int = None,
        retries: int = None,
        retry_delay: float = None,
        viewport: dict = None,
        user_agent: str = None,
        proxy: dict = None,
        block_images: bool = None,
        block_fonts: bool = None,
        storage_state: str = None,
    ):
        self.headless = headless if headless is not None else settings.HEADLESS
        self.timeout = timeout if timeout is not None else settings.TIMEOUT
        self.retries = retries if retries is not None else settings.RETRIES
        self.retry_delay = retry_delay if retry_delay is not None else settings.RETRY_DELAY
        self.viewport = viewport or settings.VIEWPORT
        self.user_agent = user_agent or settings.USER_AGENT
        self.proxy = proxy or settings.PROXY
        self.block_images = block_images if block_images is not None else settings.BLOCK_IMAGES
        self.block_fonts = block_fonts if block_fonts is not None else settings.BLOCK_FONTS
        self.storage_state = storage_state

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    # ------------------------------------------------
    # Init / Close
    # ------------------------------------------------

    async def init(self):
        self._playwright = await async_playwright().start()

        launch_opts = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        }

        # ✅ UAE proxy
        if self.proxy:
            launch_opts["proxy"] = self.proxy

        self._browser = await self._playwright.chromium.launch(**launch_opts)

        # ✅ FIX: ignore HTTPS errors for proxy
        context_opts = {
            "viewport": self.viewport,
            "ignore_https_errors": True,
            "locale": "en-US",
            "timezone_id": "Asia/Dubai",
        }

        if self.user_agent:
            context_opts["user_agent"] = self.user_agent

        if self.storage_state:
            context_opts["storage_state"] = self.storage_state
            log.info(f"Loaded storage state: {self.storage_state}")

        self._context = await self._browser.new_context(**context_opts)

        self._context.set_default_timeout(self.timeout)

        # ✅ resource blocking
        if self.block_images or self.block_fonts:
            await self._context.route("**/*", self._block_resources)

        log.info("🌐 Browser ready (proxy + SSL fixed)")

        return self

    async def close(self):

        if self._browser:
            await self._browser.close()

        if self._playwright:
            await self._playwright.stop()

        log.info("🔒 Browser closed")

    async def __aenter__(self):
        return await self.init()

    async def __aexit__(self, *_):
        await self.close()

    # ------------------------------------------------
    # Core scraping
    # ------------------------------------------------

    async def new_page(self):
        if not self._context:
            raise RuntimeError("Call await scraper.init() first")

        return await self._context.new_page()

    async def scrape(
        self,
        url: str,
        fn: Callable[[Page], Awaitable[Any]],
        wait_until: str = "domcontentloaded",
        timeout: int = 60000,
    ) -> Any:

        if not self._context:
            raise RuntimeError("Call await scraper.init() first")

        last_error = None

        for attempt in range(1, self.retries + 2):

            page = await self._context.new_page()
            response = None

            try:

                log.info(f"🔍 [{attempt}] Scraping: {url}")

                response = await page.goto(
                    url,
                    wait_until=wait_until,
                    timeout=timeout or self.timeout
                )

                result = await fn(page)

                if not result:
                    raise ValueError("Empty result from parser")

                log.success(f"Done: {url}")
                return result

            except Exception as e:

                # a block page (403 etc.) otherwise only shows up as a selector timeout
                status = f" [HTTP {response.status}]" if response else ""
                last_error = f"{e}{status}"
                log.warning(f"⚠️ Attempt {attempt} failed{status}: {e}")

                if attempt <= self.retries:
                    await asyncio.sleep(self.retry_delay)

            finally:
                await page.close()

        raise RuntimeError(f"Failed after retries on {url}: {last_error}")

    async def scrape_many(self, tasks: list[dict], concurrency: int = 3):

        semaphore = asyncio.Semaphore(concurrency)

        async def _run(task):

            url = task["url"]
            fn = task["fn"]
            opts = task.get("opts", {})

            async with semaphore:

                try:
                    await asyncio.sleep(0.3)

                    data = await self.scrape(url, fn, **opts)

                    if not data:
                        return {"url": url, "error": "empty_data"}

                    return {"url": url, "data": data}

                except Exception as e:
                    return {"url": url, "error": str(e)}

        return await asyncio.gather(*[_run(t) for t in tasks])

    # ------------------------------------------------
    # Resource blocking
    # ------------------------------------------------

    async def _block_resources(self, route):

        resource_type = route.request.resource_type

        if (
            (self.block_images and resource_type == "image")
            or
            (self.block_fonts and resource_type == "font")
        ):
            await route.abort()
        else:
            await route.continue_()