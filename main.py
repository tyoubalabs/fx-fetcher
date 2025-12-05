from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import asyncio, re, json, time, os

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_FILE = "fx_rates.json"

# --- MoneyGram scraper ---
async def fetch_moneygram_rate(from_currency: str, to_currency: str) -> float | None:
    key = (from_currency.upper(), to_currency.upper())
    if key not in MG_CONFIG:
        return None
    url = MG_CONFIG[key]
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Try to locate the exchange rate span
            locator = page.locator(
                'xpath=//*[@id="main"]/div[1]/div/div/div/div[2]/div/form/div[1]/div[2]/div[1]/div[2]/span[2]'
            )
            await locator.wait_for(timeout=60000)
            text = await locator.inner_text()
            print(f"[MG DEBUG] {from_currency}->{to_currency}: {text}")

            # Extract numeric rate
            text = text.split("=")[1].strip() if "=" in text else text
            match = re.search(r"([\d.]+)", text)
            print("[MG RATE ADDED]")
            await browser.close()
            return float(match.group(1)) if match else None
    except Exception as e:
        print(f"[MG ERROR] {from_currency}->{to_currency}: {e}")
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
}

#--- Moneygram config ---
MG_CONFIG = {
    ("CAD", "TND"): "https://www.moneygram.com/ca/en/corridor/tunisia",
    ("CAD", "MAD"): "https://www.moneygram.com/ca/en/corridor/morocco",
    ("USD", "MAD"): "https://www.moneygram.com/us/en/corridor/morocco",
    ("USD", "TND"): "https://www.moneygram.com/us/en/corridor/tunisia",
    ("EUR", "TND"): "https://www.moneygram.com/fr/en/corridor/tunisia",
    ("EUR", "MAD"): "https://www.moneygram.com/fr/en/corridor/morocco",
}

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
            match = re.search(r"([\d.]+)", text)
            print("[WU RATE ADDED]")
            await browser.close()
            return float(match.group(1)) if match else None
    except Exception as e:
        print("[WU ERROR]", e)
        return None

# --- Refresh endpoint ---
@app.get("/refresh")
async def refresh():
    # Write a placeholder so /wu doesn’t error
    with open(CACHE_FILE, "w") as f:
        json.dump({"timestamp": time.time(), "rates": {}}, f)

    # Schedule the heavy scrape
    asyncio.create_task(refresh_rates_once())
    return {"status": "refresh scheduled"}

async def refresh_rates_once():
    # Load existing cache if it exists
    old_cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                old_cache = json.load(f)
        except Exception as e:
            print("[CACHE ERROR] Failed to read old cache:", e)

    old_rates = old_cache.get("rates", {})

    results = {}
    # --- Western Union pairs ---
    for (from_cur, to_cur) in WU_CONFIG.keys():
        try:
            rate = await fetch_wu_rate(from_cur, to_cur)
            if rate is not None:
                results[f"WU_{from_cur}_{to_cur}"] = rate
            else:
                results[f"WU_{from_cur}_{to_cur}"] = old_rates.get(f"WU_{from_cur}_{to_cur}")
                print(f"[WU ERROR] {from_cur}->{to_cur} scrape failed, kept old value {results[f'WU_{from_cur}_{to_cur}']}")
        except Exception as e:
            results[f"WU_{from_cur}_{to_cur}"] = old_rates.get(f"WU_{from_cur}_{to_cur}")
            print(f"[WU EXCEPTION] {from_cur}->{to_cur}: {e}, kept old value {results[f'WU_{from_cur}_{to_cur}']}")
            
    # --- MoneyGram pairs ---
    for (from_cur, to_cur) in MG_CONFIG.keys():
        try:
            rate = await fetch_moneygram_rate(from_cur, to_cur)
            if rate is not None:
                results[f"MG_{from_cur}_{to_cur}"] = rate
            else:
                # fallback to old value
                results[f"MG_{from_cur}_{to_cur}"] = old_rates.get(f"MG_{from_cur}_{to_cur}")
                print(f"[MG ERROR] {from_cur}->{to_cur} scrape failed, kept old value {results[f'MG_{from_cur}_{to_cur}']}")
        except Exception as e:
            results[f"MG_{from_cur}_{to_cur}"] = old_rates.get(f"MG_{from_cur}_{to_cur}")
            print(f"[MG EXCEPTION] {from_cur}->{to_cur}: {e}, kept old value {results[f'MG_{from_cur}_{to_cur}']}")



    # --- Write new cache ---
    new_cache = {"timestamp": time.time(), "rates": results}
    with open(CACHE_FILE, "w") as f:
        json.dump(new_cache, f)

    print("[CACHE UPDATED]")
    print("[CACHE CONTENT]", json.dumps(new_cache, indent=2))


# --- Endpoints that read cache ---
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
