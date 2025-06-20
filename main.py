from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import asyncio
import re

app = FastAPI()
# دالة مساعدة لاستخلاص بيانات من كوبارت
async def scrape_copart(lot: str):
    url = f"https://www.copart.com/lot/{lot}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
           await page.goto(url, timeout=10000)  # 10 ثواني فقط
await page.wait_for_selector(".lot-detail", timeout=5000)  # 5 ثواني فقط


            # مثال: جلب سنة الصنع، الماركة، الموديل من صفحة كوبارت
            title = await page.locator(".lot-detail h1").inner_text()
            # مثال: عنوان النموذج: "2020 TOYOTA CAMRY"
            match = re.match(r"(\d{4})\s+([A-Z]+)\s+(.+)", title, re.I)
            year, make, model = None, None, None
            if match:
                year, make, model = match.group(1), match.group(2), match.group(3)

            vin = await page.locator("xpath=//span[contains(text(),'VIN')]/following-sibling::span").inner_text()
            damage_desc = await page.locator(".lot-damage-description").inner_text()
            odometer = await page.locator("xpath=//span[contains(text(),'Odometer')]/following-sibling::span").inner_text()
            auction_date = await page.locator(".auction-date").inner_text()
            location = await page.locator(".auction-location").inner_text()
            sale_status = await page.locator(".sale-status").inner_text()

            # صور (مجموعة) — مثلا في كوبارت الصور داخل عناصر img ضمن div معين
            images = await page.locator(".gallery-image img").all_attribute("src")

            await browser.close()

            return {
                "platform": "copart",
                "lot_number": lot,
                "year": year,
                "make": make,
                "model": model,
                "vin": vin,
                "damage_description": damage_desc,
                "odometer": odometer,
                "auction_date": auction_date,
                "auction_location": location,
                "sale_status": sale_status,
                "images": images,
            }

        except PlaywrightTimeout:
            await browser.close()
            raise HTTPException(status_code=404, detail="Copart lot not found or page took too long to load")


# دالة مساعدة لاستخلاص بيانات من IAA
async def scrape_iaa(lot: str):
    url = f"https://www.iaai.com/VehicleDetails/{lot}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
          await page.goto(url, timeout=10000)  # 10 ثواني فقط
await page.wait_for_selector(".lot-detail", timeout=5000)  # 5 ثواني فقط


            # مثال جلب بيانات مشابهة من IAA
            title = await page.locator(".vehicle-title").inner_text()
            match = re.match(r"(\d{4})\s+([A-Z]+)\s+(.+)", title, re.I)
            year, make, model = None, None, None
            if match:
                year, make, model = match.group(1), match.group(2), match.group(3)

            vin = await page.locator("xpath=//dt[text()='VIN']/following-sibling::dd[1]").inner_text()
            damage_desc = await page.locator(".damage-description").inner_text()
            odometer = await page.locator("xpath=//dt[text()='Odometer']/following-sibling::dd[1]").inner_text()
            auction_date = await page.locator(".auction-date").inner_text()
            location = await page.locator(".auction-location").inner_text()
            sale_status = await page.locator(".sale-status").inner_text()

            images = await page.locator(".image-gallery img").all_attribute("src")

            await browser.close()

            return {
                "platform": "iaai",
                "lot_number": lot,
                "year": year,
                "make": make,
                "model": model,
                "vin": vin,
                "damage_description": damage_desc,
                "odometer": odometer,
                "auction_date": auction_date,
                "auction_location": location,
                "sale_status": sale_status,
                "images": images,
            }

        except PlaywrightTimeout:
            await browser.close()
            raise HTTPException(status_code=404, detail="IAA lot not found or page took too long to load")


# دالة رئيسية لتحديد الموقع واختيار الـ scraper المناسب
@app.get("/api/get_vehicle_data")
async def get_vehicle_data(lot: str = Query(None), url: str = Query(None)):
    if not lot and not url:
        raise HTTPException(status_code=400, detail="Must provide lot number or url")

    # تحديد المنصة حسب url أو رقم اللوت
    target_lot = lot
    platform = None

    if url:
        if "copart.com" in url:
            platform = "copart"
            # استخراج رقم اللوت من الرابط
            match = re.search(r"/lot/(\d+)", url)
            if not match:
                raise HTTPException(status_code=400, detail="Invalid Copart URL format")
            target_lot = match.group(1)

        elif "iaai.com" in url:
            platform = "iaai"
            match = re.search(r"/VehicleDetails/(\d+)", url)
            if not match:
                raise HTTPException(status_code=400, detail="Invalid IAA URL format")
            target_lot = match.group(1)

        else:
            raise HTTPException(status_code=400, detail="Unsupported URL domain")

    else:
        # لو لا يوجد url، نعتمد على رقم اللوت ونجرب تحديد الموقع
        if lot.isdigit() and len(lot) >= 5:
            # لتبسيط، افترض أن الأرقام التي تبدأ بـ 5+ هي كوبارت، و 4+ هي IAA (تعديل حسب حاجتك)
            if lot.startswith("5") or lot.startswith("3"):
                platform = "copart"
            else:
                platform = "iaai"
        else:
            raise HTTPException(status_code=400, detail="Invalid lot number format")

    # نوجه للـ scraper المناسب
    if platform == "copart":
        return await scrape_copart(target_lot)
    elif platform == "iaai":
        return await scrape_iaa(target_lot)
    else:
        raise HTTPException(status_code=400, detail="Unsupported platform")


# لتشغيل محلي:
# uvicorn main:app --reload
