from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import re, asyncio, json, time, os

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to your app domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_FILE = "fx_rates.json"

# --- MoneyGram scraper ---
async def fetch_moneygram_rate() -> float | None:
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
            print("[MG DEBUG]", text)
            text = text.split("=")[1].strip()
            rate = re.search(r"([\d.]+)", text).group(1)
            await browser.close()
            return float(rate)
    except Exception as e:
        print("[MG ERROR]", e)
        return None


# --- Western Union config ---
WU_CONFIG = {
    ("CAD", "TND"): {
        "url": "https://www.westernunion.com/ca/en/send-money-to-tunisia.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
    ("CAD", "MAD"): {
        "url": "https://www.westernunion.com/ca/en/send-money-to-morocco.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
    ("USD", "TND"): {
        "url": "https://www.westernunion.com/us/en/currency-converter/usd-to-tnd-rate.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[3]/p/span[1]/span[1]/span/span'
    },
    ("USD", "MAD"): {
        "url": "https://www.westernunion.com/us/en/currency-converter/usd-to-mad-rate.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[3]/p/span[1]/span[1]/span/span'
    },
    ("EUR", "TND"): {
        "url": "https://www.westernunion.com/fr/en/send-money-to-tunisia.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
    ("EUR", "MAD"): {
        "url": "https://www.westernunion.com/fr/en/send-money-to-morocco.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
}

async def fetch_wu_rate(from_currency: str, to_currency: str) -> float | None:
    key = (from_currency.upper(), to_currency.upper())
    if key not in WU_CONFIG:
        return None
    config = WU_CONFIG[key]
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = await browser.new_page()
            await page.goto(config["url"], wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector(config["selector"], timeout=60000)
            text = await page.locator(config["selector"]).inner_text()
            print(f"[WU DEBUG] {from_currency}->{to_currency}: {text}")
            match = re.search(r"([\d.]+)", text)
            await browser.close()
            return float(match.group(1)) if match else None
    except Exception as e:
        print("[WU ERROR]", e)
        return None


# --- Background caching loop ---
async def refresh_rates():
    while True:
        results = {}
        # MoneyGram
        results["MoneyGram"] = await fetch_moneygram_rate()
        # Western Union pairs
        for (from_cur, to_cur) in WU_CONFIG.keys():
            results[f"WU_{from_cur}_{to_cur}"] = await fetch_wu_rate(from_cur, to_cur)
        with open(CACHE_FILE, "w") as f:
            json.dump({"timestamp": time.time(), "rates": results}, f)
        print("[CACHE UPDATED]")
        await asyncio.sleep(900)  # 15 minutes


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(refresh_rates())


# --- Endpoints ---
@app.get("/moneygram")
async def moneygram():
    if not os.path.exists(CACHE_FILE):
        return {"MoneyGram": None, "error": "Cache not ready"}
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
    return {"MoneyGram": cache["rates"].get("MoneyGram"), "cached_at": cache["timestamp"]}


@app.get("/wu")
async def wu(from_currency: str = Query(...), to_currency: str = Query(...)):
    if not os.path.exists(CACHE_FILE):
        return {"Western_Union": None, "error": "Cache not ready"}
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
    key = f"WU_{from_currency.upper()}_{to_currency.upper()}"
    return {"Western_Union": cache["rates"].get(key), "cached_at": cache["timestamp"]}


@app.get("/ping")
def ping():
    return {"status": "ok"}
