# generate_session.py

import asyncio
from playwright.async_api import async_playwright

async def main():

    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        page = await context.new_page()

        await page.goto(url='https://www.jmkcellars.com')

        print("\nSelect Dubai manually in the browser...")
        input("Press ENTER after selecting location")

        await context.storage_state(path="sessions/africaneasternabudhabi.json")

        print("Session saved")

        await browser.close()

asyncio.run(main())