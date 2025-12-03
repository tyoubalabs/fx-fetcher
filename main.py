from fastapi import FastAPI, Query
from playwright.async_api import async_playwright
import re

app = FastAPI()

async def scrape_moneygram(from_country: str, to_country: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        url = f"https://www.moneygram.com/{from_country}/en/corridor/{to_country}"
        await page.goto(url, wait_until="domcontentloaded")
        text = await page.locator('xpath=//*[@id="main"]/div[1]/div/div/div/div[2]/div/form/div[1]/div[2]/div[1]/div[2]/span[2]').inner_text()
        await browser.close()
        return float(re.search(r"([\d.]+)", text).group(1))

async def scrape_wu(from_country: str, to_country: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        url = f"https://www.westernunion.com/{from_country}/en/send-money-to-{to_country}.html"
        await page.goto(url, wait_until="domcontentloaded")
        text = await page.locator('xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span').inner_text()
        await browser.close()
        return float(re.search(r"([\d.]+)", text).group(1))

@app.get("/moneygram")
async def moneygram(from_country: str = Query("ca"), to_country: str = Query("tunisia")):
    try:
        rate = await scrape_moneygram(from_country, to_country)
        return {"provider": "MoneyGram", "rate": rate}
    except Exception as e:
        return {"provider": "MoneyGram", "rate": None, "error": str(e)}

@app.get("/wu")
async def western_union(from_country: str = Query("ca"), to_country: str = Query("tunisia")):
    try:
        rate = await scrape_wu(from_country, to_country)
        return {"provider": "Western Union", "rate": rate}
    except Exception as e:
        return {"provider": "Western Union", "rate": None, "error": str(e)}
