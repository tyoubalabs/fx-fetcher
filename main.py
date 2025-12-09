from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import re, json, time, os
import asyncio
import logging
import urllib.request
import json
import webbrowser
from urllib.parse import urlencode

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_FILE = "fx_rates.json"
TEMP_CACHE_FILE = "tmp_fx_rates.json"


# --- Moneygram config ---        
MONEYGRAM_CONFIG = {
    ("CAD", "TND"): {
        "senderCountryCode": "CAN",
        "senderCurrencyCode": "CAD",
        "receiverCountryCode": "TUN",
        "sendAmount": "100"
    },
    ("CAD", "MAD"): {
        "senderCountryCode": "CAN",
        "senderCurrencyCode": "CAD",
        "receiverCountryCode": "MAR",
        "sendAmount": "100"
    },
    ("CAD", "MXN"): {
        "senderCountryCode": "CAN",
        "senderCurrencyCode": "CAD",
        "receiverCountryCode": "MEX",
        "sendAmount": "100"
    },
    ("USD", "TND"): {
        "senderCountryCode": "USA",
        "senderCurrencyCode": "USD",
        "receiverCountryCode": "TUN",
        "sendAmount": "250"
    },     
    ("USD", "MXN"): {
        "senderCountryCode": "USA",
        "senderCurrencyCode": "USD",
        "receiverCountryCode": "MEX",
        "sendAmount": "250"
    },  
    ("USD", "MAD"): {
        "senderCountryCode": "USA",
        "senderCurrencyCode": "USD",
        "receiverCountryCode": "MAR",
        "sendAmount": "100"
    }, 
    ("EUR", "MAD"): {
        "senderCountryCode": "FRA",
        "senderCurrencyCode": "EUR",
        "receiverCountryCode": "MAR",
        "sendAmount": "100"
    }, 
    ("EUR", "TND"): {
        "senderCountryCode": "FRA",
        "senderCurrencyCode": "EUR",
        "receiverCountryCode": "TUN",
        "sendAmount": "100"
    },
    ("EUR", "MXN"): {
        "senderCountryCode": "FRA",
        "senderCurrencyCode": "EUR",
        "receiverCountryCode": "MEX",
        "sendAmount": "100"
    },    
}


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
    ("EUR", "MXN"): {
        "url": "https://www.westernunion.com/fr/en/send-money-to-mexico.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
    ("CAD", "MXN"): {
        "url": "https://www.westernunion.com/ca/fr/send-money-to-mexico.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/strong/span'
    },  
    ("USD", "MXN"): {
        "url": "https://www.westernunion.com/us/en/currency-converter/usd-to-mxn-rate.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[3]/p/span[1]/span[1]/span/span'
    },     
}

# --- MoneyGram scraper ---
async def fetch_moneygram_rate(from_currency: str, to_currency: str) -> float | None:
    # Look up parameters from config
    params = MONEYGRAM_CONFIG.get((from_currency, to_currency))
    if not params:
        raise ValueError(f"No config found for {from_currency}->{to_currency}")

    # Build query string dynamically
    query = urlencode(params)
    url = f"https://www.moneygram.com/api/send-money/fee-quote/v2?{query}"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
            page = await browser.new_page()

            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)  # wait 2 seconds

            # Extract JSON text from <pre>
            raw_text = await page.inner_text("pre")
            data = json.loads(raw_text)

            # Try to extract fxRate for whichever receive currency is present
            fee_quotes = data.get("feeQuotesByCurrency", {})
            fx_rate = None
            if fee_quotes:
                # Grab the first currency’s fxRate
                first_currency = next(iter(fee_quotes))
                fx_rate = fee_quotes[first_currency].get("fxRate")

            await browser.close()
            return fx_rate
    except Exception as e:
        logging.error(f"[MG EXCEPTION] {from_currency}->{to_currency}: {e}")
        return None

# --- Western Union scraper ---        
async def fetch_wu_rate(from_currency: str, to_currency: str) -> float | None:
    key = (from_currency.upper(), to_currency.upper())
    if key not in WU_CONFIG:
        return None
    config = WU_CONFIG[key]
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(config["url"], wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector(config["selector"], timeout=60000)
            text = await page.locator(config["selector"]).inner_text()
            match = re.search(r"([\d.,]+)", text)
            await browser.close()
            logging.info("[Browser closed]")
            return match.group(1) if match else None
    except Exception as e:
        logging.error(f"[WU EXCEPTION] {from_currency}->{to_currency}: {e}")
        return None

# --- Refresh endpoint ---
async def refresh():
   while True: 
    results = {}

    for (from_cur, to_cur) in MONEYGRAM_CONFIG.keys():
        results[f"MG_{from_cur}_{to_cur}"] = await fetch_moneygram_rate(from_cur, to_cur)
        logging.info("[NEW MG RATE ADDED]")
        results[f"WU_{from_cur}_{to_cur}"] = await fetch_wu_rate(from_cur, to_cur)
        logging.info("[NEW WU RATE ADDED]")

        
    # --- Write to temp file first ---
    new_cache = {"timestamp": time.time(), "rates": results}
    with open(TEMP_CACHE_FILE, "w") as f:
        json.dump(new_cache, f)      

    # --- Atomically replace main cache file ---
    os.replace(TEMP_CACHE_FILE, CACHE_FILE)        

    logging.info("[CACHE UPDATED]")
    # sleep 15 minutes
    await asyncio.sleep(900)
   

# --- Endpoints that read cache ---
@app.get("/moneygram")
async def moneygram(from_currency: str = Query(...), to_currency: str = Query(...)):
    if not os.path.exists(CACHE_FILE):
        return {"MoneyGram": None, "error": "Cache not ready"}
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
    key = f"MG_{from_currency.upper()}_{to_currency.upper()}"
    return {"MoneyGram": cache["rates"].get(key), "cached_at": cache["timestamp"]}

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
    
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(refresh())
