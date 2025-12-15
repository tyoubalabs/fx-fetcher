from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright
import re, json, time, os
import asyncio
import logging
import urllib.request
import json
import webbrowser
from jsonpath_ng import parse
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
SESSION_FILE = "moneygram_session.json"

# --- Lemfi config ---        
LEMFI_CONFIG = {
    ("CAD", "TND"): {
        "url": "https://lemfi.com/en-ca/international-money-transfer/tunisia",
        "selector": 'xpath=//*[@id="__nuxt"]/div[2]/div[1]/div[2]/div[1]/div[1]/div[3]/div[1]/span[2]'
    },
    ("CAD", "MAD"): {
        "url": "https://lemfi.com/en-ca/international-money-transfer/morocco",
        "selector": 'xpath=//*[@id="__nuxt"]/div[2]/div[1]/div[2]/div[1]/div[1]/div[3]/div[1]/span[2]'
    },
    ("EUR", "TND"): {
        "url": "https://lemfi.com/en-fr/international-money-transfer/tunisia",
        "selector": 'xpath=//*[@id="__nuxt"]/div[2]/div[1]/div[2]/div[1]/div[1]/div[3]/div[1]/span[2]'
    },
    ("EUR", "MAD"): {
        "url": "https://lemfi.com/en-fr/international-money-transfer/morocco",
        "selector": 'xpath=//*[@id="__nuxt"]/div[2]/div[1]/div[2]/div[1]/div[1]/div[3]/div[1]/span[2]'
    },
    ("CAD", "INR"): {
        "url": "https://lemfi.com/en-ca/international-money-transfer/india",
        "selector": 'xpath=//*[@id="__nuxt"]/div[2]/div[1]/div[2]/div[1]/div[1]/div[3]/div[1]/span[2]'
    },
    ("USD", "INR"): {
        "url": "https://lemfi.com/en-us/international-money-transfer/india",
        "selector": 'xpath=//*[@id="__nuxt"]/div[2]/div[1]/div[2]/div[1]/div[1]/div[3]/div[1]/span[2]'
    },
    ("EUR", "INR"): {
        "url": "https://lemfi.com/en-fr/international-money-transfer/india",
        "selector": 'xpath=//*[@id="__nuxt"]/div[2]/div[1]/div[2]/div[1]/div[1]/div[3]/div[1]/span[2]'
    },    
}
    
# --- Moneygram config ---        
MONEYGRAM_CONFIG = {
    ("CAD", "TND"): {
        "senderCountryCode": "CAN",
        "senderCurrencyCode": "CAD",
        "receiverCountryCode": "TUN",
        "sendAmount": "100.00"
    },
    ("CAD", "MAD"): {
        "senderCountryCode": "CAN",
        "senderCurrencyCode": "CAD",
        "receiverCountryCode": "MAR",
        "sendAmount": "100.00"
    },
    ("CAD", "MXN"): {
        "senderCountryCode": "CAN",
        "senderCurrencyCode": "CAD",
        "receiverCountryCode": "MEX",
        "sendAmount": "100.00"
    },
    ("USD", "TND"): {
        "senderCountryCode": "USA",
        "senderCurrencyCode": "USD",
        "receiverCountryCode": "TUN",
        "sendAmount": "100.00"
    },     
    ("USD", "MXN"): {
        "senderCountryCode": "USA",
        "senderCurrencyCode": "USD",
        "receiverCountryCode": "MEX",
        "sendAmount": "100.00"
    },  
    ("USD", "MAD"): {
        "senderCountryCode": "USA",
        "senderCurrencyCode": "USD",
        "receiverCountryCode": "MAR",
        "sendAmount": "100.00"
    }, 
    ("EUR", "MAD"): {
        "senderCountryCode": "FRA",
        "senderCurrencyCode": "EUR",
        "receiverCountryCode": "MAR",
        "sendAmount": "100.00"
    }, 
    ("EUR", "TND"): {
        "senderCountryCode": "FRA",
        "senderCurrencyCode": "EUR",
        "receiverCountryCode": "TUN",
        "sendAmount": "100.00"
    },
    ("EUR", "MXN"): {
        "senderCountryCode": "FRA",
        "senderCurrencyCode": "EUR",
        "receiverCountryCode": "MEX",
        "sendAmount": "100.00"
    }, 
    ("CAD", "INR"): {
        "senderCountryCode": "CAN",
        "senderCurrencyCode": "CAD",
        "receiverCountryCode": "IND",
        "sendAmount": "100.00"
    },
    ("USD", "INR"): {
        "senderCountryCode": "USA",
        "senderCurrencyCode": "USD",
        "receiverCountryCode": "IND",
        "sendAmount": "100.00"
    },
    ("EUR", "INR"): {
        "senderCountryCode": "FRA",
        "senderCurrencyCode": "EUR",
        "receiverCountryCode": "IND",
        "sendAmount": "100.00"
    },    
	("CAD", "COP"): {
        "senderCountryCode": "CAN",
        "senderCurrencyCode": "CAD",
        "receiverCountryCode": "COL",
        "sendAmount": "100.00"
    },
    ("USD", "COP"): {
        "senderCountryCode": "USA",
        "senderCurrencyCode": "USD",
        "receiverCountryCode": "COL",
        "sendAmount": "100.00"
    },
    ("EUR", "COP"): {
        "senderCountryCode": "FRA",
        "senderCurrencyCode": "EUR",
        "receiverCountryCode": "COL",
        "sendAmount": "100.00"
    },
	("CAD", "TRY"): {
        "senderCountryCode": "CAN",
        "senderCurrencyCode": "CAD",
        "receiverCountryCode": "TUR",
        "sendAmount": "100.00"
    },
    ("USD", "TRY"): {
        "senderCountryCode": "USA",
        "senderCurrencyCode": "USD",
        "receiverCountryCode": "TUR",
        "sendAmount": "100.00"
    },
    ("EUR", "TRY"): {
        "senderCountryCode": "FRA",
        "senderCurrencyCode": "EUR",
        "receiverCountryCode": "TUR",
        "sendAmount": "100.00"
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
    ("EUR", "INR"): {
        "url": "https://www.westernunion.com/fr/en/send-money-to-india.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
    ("CAD", "INR"): {
        "url": "https://www.westernunion.com/ca/fr/send-money-to-india.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/strong/span'
    },  
    ("USD", "INR"): {
        "url": "https://www.westernunion.com/us/en/currency-converter/usd-to-inr-rate.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[3]/p/span[1]/span[1]/span/span'
    },
	("EUR", "TRY"): {
        "url": "https://www.westernunion.com/fr/en/send-money-to-turkey.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
    ("CAD", "TRY"): {
        "url": "https://www.westernunion.com/ca/en/send-money-to-turkey.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },  
    ("USD", "TRY"): {
        "url": "https://www.westernunion.com/us/en/currency-converter/usd-to-try-rate.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[3]/p/span[1]/span[1]/span/span'
    },
	("EUR", "COP"): {
        "url": "https://www.westernunion.com/fr/en/send-money-to-colombia.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/span/span'
    },
    ("CAD", "COP"): {
        "url": "https://www.westernunion.com/ca/fr/send-money-to-colombia.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[2]/p/span[1]/span[1]/strong/span'
    },  
    ("USD", "COP"): {
        "url": "https://www.westernunion.com/us/en/currency-converter/usd-to-cop-rate.html",
        "selector": 'xpath=//*[@id="body-component"]/section[1]/section[1]/div[1]/div/div/div[3]/p/span[1]/span[1]/span/span'
    },
}

# --- MyEasyTransfer config ---
MYEASYTRANSFER_CONFIG = {
    ("EUR", "TND"): {
        "departureCurrencyId": "623d820a0b5a9d374d8becab",   # example EUR
        "destinationCurrencyId": "65f4a7651529e3e101439541"  # example TND
    },
    ("EUR", "MAD"): {
        "departureCurrencyId": "623d820a0b5a9d374d8becab",   # EUR
        "destinationCurrencyId": "617aa96c6f86345324eb252f"  # MAD 
    },    
   
}


TARGET_ENDPOINT = "https://www.westernunion.com/router/"
US_TARGET_ENDPOINT = "https://www.westernunion.com/wuconnect/prices/catalog"

# --- MyEasyTransfer scraper ---
async def fetch_myeasytransfer_rate(from_currency: str, to_currency: str) -> float | None:
    params = MYEASYTRANSFER_CONFIG.get((from_currency, to_currency))
    if not params:
        logging.error(f"[EASYTR ERROR] Unsupported pair {from_currency}->{to_currency}")
        return None

    query = urlencode(params)
    url = f"https://www.api.myeasytransfer.com/v1/fxrates/fxrate?{query}"
    logging.debug(f"[EASYTR] url: {url}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            raw_text = await page.inner_text("pre")
            data = json.loads(raw_text)
            logging.info(f"[MyEasyTransfer RAW TEXT] {from_currency}->{to_currency}: {raw_text}")
            fx_rate_bank = data["fxRate"]["fxRateBank"]
            await browser.close()
            return fx_rate_bank
    except Exception as e:
        logging.error(f"[MyEasyTransfer EXCEPTION] {from_currency}->{to_currency}: {e}")
        return None

# --- MoneyGram scraper ---
async def fetch_moneygram_rate(from_currency: str, to_currency: str) -> float | None:
    # Look up parameters from config
    params = MONEYGRAM_CONFIG.get((from_currency, to_currency))
    if not params:
        raise ValueError(f"No config found for {from_currency}->{to_currency}")
        return None

    # Build query string dynamically
    query = urlencode(params)
    url = f"https://www.moneygram.com/api/send-money/fee-quote/v2?{query}"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
            # Reuse cookies/local storage
            context = await browser.new_context(storage_state=SESSION_FILE if os.path.exists(SESSION_FILE) else None)
            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)  # wait 2 seconds

            # Extract JSON text from <pre>
            raw_text = await page.inner_text("pre")
            data = json.loads(raw_text)
            # Save session state for next run
            await context.storage_state(path=SESSION_FILE)
            logging.info(f"[MG RAW TEXT] {from_currency}->{to_currency}: {raw_text}")
            # Try to extract fxRate for whichever receive currency is present
            fee_quotes = data.get("feeQuotesByCurrency", {})
            fx_rate = None
            if fee_quotes and to_currency in fee_quotes:
                fx_rate = fee_quotes[to_currency].get("fxRate")

            await browser.close()
            return fx_rate
    except Exception as e:
        logging.error(f"[MG EXCEPTION] {from_currency}->{to_currency}: {e}")
        return None
    

# --- Western Union scraper ---
async def fetch_wu_rate(from_currency: str, to_currency: str):
    """Fetch strikeExchangeRate for given currency pair from Western Union."""
    config = WU_CONFIG.get((from_currency, to_currency))
    if not config:
        raise ValueError(f"No config found for {from_currency} → {to_currency}")

    url = config["url"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context()
        page = await context.new_page()

        async def handle_response(response):
            try:
                if response.url.startswith(TARGET_ENDPOINT):
                    #try:
                    json_data = await response.json()
                    logging.info("Captured JSON response")
					logging.info(f"json_data")
					
                    # Extract value using JSONPath
                    jsonpath_expr = parse("$.data.products.products[7].strikeExchangeRate")
                    matches = [match.value for match in jsonpath_expr.find(json_data)]
                    rate = round(float(matches[0]), 4)

                    if matches:
                        logging.info(f"{from_currency}->{to_currency} strikeExchangeRate:", rate)
                    else:
                        logging.info("Could find the rate")    
                elif from_currency.upper() != "CAD" and US_TARGET_ENDPOINT in response.url:
                    json_data = await response.json()
                    logging.info("Captured JSON response")

                    # Extract value using JSONPath
                    if from_currency.upper() == "USD": jsonpath_expr = parse("$.categories[0].services[0].strike_fx_rate")
                    if from_currency.upper() == "EUR": jsonpath_expr = parse("$.services_groups[1].pay_groups[0].strike_fx_rate")
                    matches = [match.value for match in jsonpath_expr.find(json_data)]
                    rate = round(float(matches[0]), 4)
                    if matches:
                        logging.info(f"{from_currency}->{to_currency} strikeExchangeRate:", rate)
                    else:
                        logging.info("Could find the rate")        
            except Exception as e:
                logging.info("Could not parse JSON:", e)

        page.on("response", handle_response)

        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(15000)

        await browser.close()
        
# --- Lemfi scraper ---
async def fetch_lemfi_rate(from_currency: str, to_currency: str) -> float | None:
    key = (from_currency.upper(), to_currency.upper())
    if key not in LEMFI_CONFIG:
        logging.error(f"[LemFi ERROR] Unsupported pair {from_currency}->{to_currency}")
        return None
        
    config = LEMFI_CONFIG[key]
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            page = await browser.new_page()
            await page.goto(config["url"], wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)  # wait 3 seconds
            await page.wait_for_selector(config["selector"], timeout=30000)
            text = await page.locator(config["selector"]).inner_text()
            text = text.split("=")[1].strip()
            rate = re.search(r"([\d.,]+)", text).group(1)
            logging.info(f"[LemFi RAW TEXT] {from_currency}->{to_currency}: {text}")
			
            await browser.close()
            return rate
    except Exception as e:
        logging.error(f"[LemFi EXCEPTION] {from_currency}->{to_currency}: {e}")
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
        results[f"LEMFI_{from_cur}_{to_cur}"] = await fetch_lemfi_rate(from_cur, to_cur)
        logging.info("[NEW LEMFI RATE ADDED]")
        results[f"MET_{from_cur}_{to_cur}"] = await fetch_myeasytransfer_rate(from_cur, to_cur)
        logging.info("[NEW EASYTR RATE ADDED]")

        
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
    
@app.get("/lemfi")
async def wu(from_currency: str = Query(...), to_currency: str = Query(...)):
    if not os.path.exists(CACHE_FILE):
        return {"Lemfi": None, "error": "Cache not ready"}
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
    key = f"LEMFI_{from_currency.upper()}_{to_currency.upper()}"
    return {"Lemfi": cache["rates"].get(key), "cached_at": cache["timestamp"]}    

@app.get("/myeasytransfer")
async def myeasytransfer(from_currency: str = Query(...), to_currency: str = Query(...)):
    if not os.path.exists(CACHE_FILE):
        return {"MyEasyTransfer": None, "error": "Cache not ready"}
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
    key = f"MET_{from_currency.upper()}_{to_currency.upper()}"
    return {"MyEasyTransfer": cache["rates"].get(key), "cached_at": cache["timestamp"]}

@app.get("/ping")
def ping():
    return {"status": "ok"}
    
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(refresh())
