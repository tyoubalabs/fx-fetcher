from fastapi import FastAPI, Query
from playwright.async_api import async_playwright
import re
import asyncio

app = FastAPI()

async def fetch_moneygram_rate(results):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
            page = await browser.new_page()
            await page.goto("https://www.moneygram.com/ca/en/corridor/tunisia", wait_until="domcontentloaded")

            await page.wait_for_selector(
                'xpath=//*[@id="main"]/div[1]/div/div/div/div[2]/div/form/div[1]/div[2]/div[1]/div[2]/span[2]'
            )
            text = await page.locator(
                'xpath=//*[@id="main"]/div[1]/div/div/div/div[2]/div/form/div[1]/div[2]/div[1]/div[2]/span[2]'
            ).inner_text()

            text = text.split("=")[1].strip()
            rate = re.search(r"([\d.]+)", text).group(1)
            results["MoneyGram"] = float(rate)

            await browser.close()
    except Exception:
        results["MoneyGram"] = "not found"

async def fetch_wu_rate(results):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = await browser.new_page()
            await page.goto(
                "https://www.westernunion.com/ca/en/send-money-to-tunisia.html",
                wait_until="domcontentloaded"
            )

            # Wait for the element and extract text
            locator = page.locator(
                'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
            )
            await locator.wait_for()
            text = await locator.inner_text()

            match = re.search(r"([\d.]+)", text)
            if match:
                results["Western Union"] = float(match.group(1))
            else:
                results["Western Union"] = None

            await browser.close()
    except Exception as e:
        results["Western Union"] = None
        results["error"] = str(e)

@app.get("/moneygram")
async def moneygram():
    results = {}
    await fetch_moneygram_rate(results)   # just await, no asyncio.run()
    return results
        
# Western Union (async)
@app.get("/wu")
async def wu():
    results = {}
    await fetch_wu_rate(results)   # just await, no asyncio.run()
    return results

@app.get("/ping")
def ping():
    return {"status": "ok"}
