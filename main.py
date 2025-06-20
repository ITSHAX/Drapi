from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import re
import requests

from playwright.sync_api import sync_playwright

app = FastAPI()

def scrape_copart_lot(lot_number: str) -> dict:
    url = f"https://www.copart.com/public/data/lotdetails/lotDetails/{lot_number}/USA"
    headers = {
        "accept": "application/json",
        "user-agent": "Mozilla/5.0"
    }

    r = requests.get(url, headers=headers)
    if r.status_code != 200 or "data" not in r.json():
        raise ValueError(f"Copart: Lot not found or blocked ({r.status_code})")

    data = r.json()["data"]
    return {
        "lot_number": data.get("lotNumber"),
        "year": data.get("vehicleDetails", {}).get("year"),
        "make": data.get("vehicleDetails", {}).get("make"),
        "model": data.get("vehicleDetails", {}).get("model"),
        "vin": data.get("vin"),
        "auction_location": data.get("saleLocation"),
        "damage": data.get("lotDetails", {}).get("damageDescription"),
        "odometer": data.get("odometerReading"),
        "sale_status": data.get("lotDetails", {}).get("saleStatus"),
        "auction_date": data.get("auctionDate"),
        "images": [img.get("url") for img in data.get("imagesList", [])],
        "source": "copart"
    }

def scrape_iaa_lot(lot_number: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"https://www.iaai.com/VehicleDetails/{lot_number}", timeout=60000)
        page.wait_for_timeout(3000)

        try:
            title = page.locator("h1").inner_text()
        except:
            title = "Unknown"

        try:
            vin = page.locator("text=VIN").nth(0).evaluate("el => el.nextElementSibling.textContent")
        except:
            vin = "Unknown"

        images = page.locator("img").all()
        img_urls = [img.get_attribute("src") for img in images if img.get_attribute("src") and "vehicleimages" in img.get_attribute("src")]

        browser.close()

        return {
            "lot_number": lot_number,
            "year": None,
            "make": None,
            "model": title,
            "vin": vin.strip(),
            "auction_location": "IAA.com",
            "damage": None,
            "odometer": None,
            "sale_status": None,
            "auction_date": None,
            "images": img_urls,
            "source": "iaai"
        }

def detect_platform_and_scrape(input_str: str) -> dict:
    if "copart.com" in input_str or re.match(r"^\d{8}$", input_str):
        lot_number = re.findall(r"\d{8}", input_str)[0]
        return scrape_copart_lot(lot_number)
    elif "iaai.com" in input_str:
        lot_number = re.findall(r"\d+", input_str.split("/")[-1])[0]
        return scrape_iaa_lot(lot_number)
    else:
        raise ValueError("Unsupported or invalid input")

@app.get("/api/get_vehicle_data")
def get_vehicle_data(lot: str = Query(None), url: str = Query(None)):
    input_val = lot or url
    if not input_val:
        raise HTTPException(status_code=400, detail="Provide lot or url")
    try:
        data = detect_platform_and_scrape(input_val)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))