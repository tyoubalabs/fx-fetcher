from fastapi import FastAPI, Query
from playwright.async_api import async_playwright
import re

app = FastAPI()

async def scrape_moneygram(from_country: str, to_country: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        url = f"https://www.moneygram.com/{from_country}/en/corridor/{to_country}"
        await page.goto(url, wait_until="domcontentloaded")
        text = await page.locator('xpath=//*[@id="main"]/div[1]/div/div/div/div[2]/div/form/div[1]/div[2]/div[1]/div[2]/span[2]').inner_text()
        await browser.close()
        return float(re.search(r"([\d.]+)", text).group(1))

async def fetch_wu_rate(results):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            page = await browser.new_page()
            await page.goto("https://www.westernunion.com/ca/en/send-money-to-tunisia.html", wait_until="domcontentloaded")

            await page.wait_for_selector('xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span')
            text = await page.locator('xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span').inner_text()
            rate = re.search(r"([\d.]+)", text).group(1)
            results["Western Union"] = float(rate)

            await browser.close()
    except Exception:
        results["Western Union"] = "not found"

@app.get("/moneygram")
async def moneygram(from_country: str = Query("ca"), to_country: str = Query("tunisia")):
    try:
        rate = await scrape_moneygram(from_country, to_country)
        return {"provider": "MoneyGram", "rate": rate}
    except Exception as e:
        return {"provider": "MoneyGram", "rate": None, "error": str(e)}
        
# Western Union (async)
@app.get("/wu")
asyncio.run(fetch_wu_rate(results))

@app.get("/ping")
def ping():
    return {"status": "ok"}
