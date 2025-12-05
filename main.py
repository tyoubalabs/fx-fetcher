from fastapi import FastAPI, Query
from playwright.async_api import async_playwright
from fastapi.middleware.cors import CORSMiddleware
import re

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to your app domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def fetch_moneygram_rate(results):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = await browser.new_page()
            await page.goto("https://www.moneygram.com/ca/en/corridor/tunisia", wait_until="domcontentloaded")

            await page.wait_for_selector(
                'xpath=//*[@id="main"]/div[1]/div/div/div/div[2]/div/form/div[1]/div[2]/div[1]/div[2]/span[2]'
            )
            text = await page.locator(
                'xpath=//*[@id="main"]/div[1]/div/div/div/div[2]/div/form/div[1]/div[2]/div[1]/div[2]/span[2]'
            ).inner_text()
            print(text)
            text = text.split("=")[1].strip()
            rate = re.search(r"([\d.]+)", text).group(1)
            results["MoneyGram"] = float(rate)

            await browser.close()
    except Exception as e:
        results["MoneyGram"] = "not found"
        results["error"] = str(e)


# Western Union configuration mapping
WU_CONFIG = {
    ("CAD", "EGP"): {
        "url": "https://www.westernunion.com/ca/en/send-money-to-egypt.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
    ("CAD", "TND"): {
        "url": "https://www.westernunion.com/ca/en/send-money-to-tunisia.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
    ("CAD", "MAD"): {
        "url": "https://www.westernunion.com/ca/en/send-money-to-morocco.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
    ("USD", "EGP"): {
        "url": "https://www.westernunion.com/us/en/web/send-money/start?ReceiveCountry=EG&ISOCurrency=EGP&SendAmount=100.00&FundsOut=BA&FundsIn=WUPay.html",
        "selector": 'xpath=//*[@id="smoExchangeRate"]/text()[2]'
    },
    ("USD", "TND"): {
        "url": "https://www.westernunion.com/us/en/currency-converter/usd-to-tnd-rate.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[3]/p/span[1]/span[1]/span/span'  # adjust after inspecting
    },
    ("USD", "MAD"): {
        "url": "https://www.westernunion.com/us/en/currency-converter/usd-to-mad-rate.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[3]/p/span[1]/span[1]/span/span'  # adjust after inspecting
    },
    ("EUR", "TND"): {
        "url": "https://www.westernunion.com/fr/en/send-money-to-tunisia.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
    ("EUR", "MAD"): {
        "url": "https://www.westernunion.com/fr/en/send-money-to-morocco.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
    ("EUR", "EGP"): {
        "url": "https://www.westernunion.com/de/en/web/send-money/start?ReceiveCountry=EG&ISOCurrency=EGP&SendAmount=100.00&FundsOut=BA&FundsIn=WUPay.html",
        "selector": 'xpath=//*[@id="smoExchangeRate"]/text()[2]'
    },
}


async def fetch_wu_rate(results, from_currency: str, to_currency: str):
    try:
        key = (from_currency.upper(), to_currency.upper())
        if key not in WU_CONFIG:
            results["Western_Union"] = None
            results["error"] = f"Unsupported currency pair {from_currency}->{to_currency}"
            return

        config = WU_CONFIG[key]
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = await browser.new_page()
            await page.goto(config["url"], wait_until="domcontentloaded")

            locator = page.locator(config["selector"])
            await locator.wait_for()
            text = await locator.inner_text()
            print(f"[WU DEBUG] Captured text for {from_currency}->{to_currency}: {text}")

            match = re.search(r"([\d.]+)", text)
            if match:
                results["Western_Union"] = float(match.group(1))
            else:
                results["Western_Union"] = None

            await browser.close()
    except Exception as e:
        results["Western_Union"] = None
        results["error"] = str(e)


@app.get("/moneygram")
async def moneygram():
    results = {}
    await fetch_moneygram_rate(results)
    return results


@app.get("/wu")
async def wu(from_currency: str = Query(...), to_currency: str = Query(...)):
    results = {}
    await fetch_wu_rate(results, from_currency, to_currency)
    return results


@app.get("/ping")
def ping():
    return {"status": "ok"}
