import time
import re
import json
import logging
import os
import asyncio
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()


# ---------------- HELPERS ----------------

def extract_cid_from_url(url):
    match = re.search(r'!1s([^!]+)!', url)
    return match.group(1) if match else "N/A"


async def extract_single_address(page):
    # Desktop layout
    try:
        addr = await page.locator('(//div[@class="rogA2c "])[1]').inner_text()
        logger.info("Address extracted using desktop selector.")
        return addr.strip()
    except:
        pass

    # New 2024+ layout
    try:
        addr = await page.locator(
            '//button[@data-item-id="address"]//div[contains(@class,"Io6YTe")]'
        ).inner_text()
        logger.info("Address extracted using new 2024+ selector.")
        return addr.strip()
    except:
        pass

    # Fallback
    try:
        blocks = page.locator('//div[contains(@class,"Io6YTe")]')
        count = await blocks.count()
        for i in range(count):
            txt = (await blocks.nth(i).inner_text()).strip()
            if len(txt) > 5 and any(ch.isdigit() for ch in txt):
                logger.info("Address extracted using fallback Io6YTe selector.")
                return txt
    except:
        pass

    logger.warning("Failed to extract address using all selectors.")
    return "N/A"


async def extract_multi_address(card):
    # Icon layout
    try:
        addr = await card.locator(
            './/div[@class="W4Efsd"][1]/span[3]/span[2]'
        ).inner_text()
        return addr.strip()
    except:
        pass

    # No icon layout
    try:
        addr = await card.locator(
            './/div[@class="W4Efsd"][1]/span[2]/span[2]'
        ).inner_text()
        return addr.strip()
    except:
        pass

    return "N/A"


# ---------------- SCRAPER CORE ----------------

async def scrape_google_maps(location, keyword):
    logger.info(f"Scraping: location='{location}', keyword='{keyword}'")

    url = f"https://www.google.com/maps/place/{location}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        search_query = f"{keyword} near {location.replace('+', ' ')}"
        logger.info(f"Searching for: {search_query}")

        await page.fill("#searchboxinput", search_query)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(5000)

        # Detect single result
        feed_exists = await page.locator('//div[@role="feed"]').count()

        if feed_exists == 0:
            logger.info("Detected SINGLE result page.")

            try:
                name = await page.locator('//h1[contains(@class,"DUwDvf")]').inner_text()
            except:
                name = "N/A"

            address = await extract_single_address(page)

            try:
                rating = await page.locator('//div[contains(@class,"F7nice")]').inner_text()
            except:
                rating = "N/A"

            try:
                reviews = await page.locator('//span[contains(@class,"UY7F9")]').inner_text()
            except:
                reviews = "N/A"

            if reviews == "N/A" or not any(ch.isdigit() for ch in reviews):
                logger.info("Single result has no reviews — skipping.")
                await browser.close()
                return []

            cid = extract_cid_from_url(page.url)

            await browser.close()
            return [{
                "name": name,
                "address": address,
                "rating": rating,
                "reviews": reviews,
                "cid": cid
            }]

        # MULTIPLE RESULTS
        logger.info("Detected MULTIPLE results page.")

        scroll_area = page.locator('//div[@role="feed"]')

        # Scroll until end
        last_height = 0
        same_count = 0

        while True:
            await scroll_area.evaluate("el => el.scrollTop = el.scrollHeight")
            await page.wait_for_timeout(2000)

            new_height = await scroll_area.evaluate("el => el.scrollHeight")

            if new_height == last_height:
                same_count += 1
            else:
                same_count = 0

            if same_count >= 3:
                break

            last_height = new_height

        cards = page.locator('.Nv2PK')
        count = await cards.count()
        logger.info(f"Found {count} raw results.")

        extracted = []

        for i in range(count):
            card = cards.nth(i)

            try:
                name = await card.locator('.qBF1Pd').inner_text()
            except:
                name = "N/A"

            address = await extract_multi_address(card)

            try:
                rating = await card.locator('.MW4etd').inner_text()
            except:
                rating = "N/A"

            try:
                reviews = await card.locator('.UY7F9').inner_text()
            except:
                reviews = "N/A"

            if reviews == "N/A" or not any(ch.isdigit() for ch in reviews):
                continue

            try:
                href = await card.locator("a").get_attribute("href")
                cid = extract_cid_from_url(href)
            except:
                cid = "N/A"

            extracted.append({
                "name": name,
                "address": address,
                "rating": rating,
                "reviews": reviews,
                "cid": cid
            })

        await browser.close()
        return extracted


# ---------------- FASTAPI ENDPOINT ----------------

@app.get("/scrape")
async def scrape_endpoint(location: str, keyword: str):
    data = await scrape_google_maps(location, keyword)
    return JSONResponse(content=data)


@app.get("/health")
def health():
    return {"status": "ok"}
