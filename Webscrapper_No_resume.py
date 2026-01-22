from playwright.sync_api import sync_playwright
import csv
import time
from datetime import datetime

# ================= CONFIG =================

START_INDEX = 0      # to resume where left off
MAX_COUNT = 10       # number of listings to extract
OUTPUT_CSV = f"acre_land_details_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# ================= SELECTORS =================

LISTING_CARD = "a[href*='/listing/']"
PRICE_SEL = "text=₹"
TITLE_SEL = "h1"
FIELDS = [
    "title", "price", "area", "area_unit",
    "district", "state", "address"
]

# ================= SCRIPT =================

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    print("🌐 Opening https://1acre.in ...")
    page.goto("https://1acre.in")
    page.wait_for_timeout(5000)

    # Scroll to load initial listings
    for _ in range(5):
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(1500)

    listings = page.locator(LISTING_CARD)
    count = listings.count()

    print(f"🔍 Found {count} listing cards on page")

    # Prepare CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "listing_index", "land_id", "title",
            "price", "area", "area_unit",
            "district", "state", "address"
        ])

        saved = 0
        i = START_INDEX

        while saved < MAX_COUNT and i < count:
            try:
                print(f"➡ Processing listing {i+1}/{count}")
                card = listings.nth(i)
                href = card.get_attribute("href")
                listing_id = href.split("/")[-1].split("?")[0]

                card.scroll_into_view_if_needed()
                card.click()
                page.wait_for_timeout(3000)

                # extract details
                title = page.locator(TITLE_SEL).first.inner_text() if page.locator(TITLE_SEL).count() else None
                price = page.locator(PRICE_SEL).first.inner_text() if page.locator(PRICE_SEL).count() else None

                # Attempt to parse structured fields from popup
                area = None
                area_unit = None
                district = None
                state = None
                address = None

                # Look for area text
                area_elem = page.locator("text=Area")
                if area_elem.count():
                    raw = area_elem.first.inner_text()
                    parts = raw.split(" ")
                    if len(parts) >= 2:
                        area = parts[1]
                        area_unit = parts[-1]

                district_elem = page.locator("text=District")
                if district_elem.count():
                    district = district_elem.first.inner_text().split(":")[-1].strip()

                state_elem = page.locator("text=State")
                if state_elem.count():
                    state = state_elem.first.inner_text().split(":")[-1].strip()

                addr_elem = page.locator("text=Address")
                if addr_elem.count():
                    address = addr_elem.first.inner_text().split(":")[-1].strip()

                writer.writerow([
                    i+1,
                    listing_id,
                    title,
                    price,
                    area,
                    area_unit,
                    district,
                    state,
                    address
                ])
                f.flush()

                saved += 1
                print(f"✅ Saved {saved}/{MAX_COUNT}")

                # close popup or return to list
                page.keyboard.press("Escape")
                page.wait_for_timeout(1500)

            except Exception as e:
                print(f"⚠️ Skipped listing {i+1}: {e}")
                try:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)
                except:
                    pass

            i += 1

    print("\n🎉 DONE")
    print(f"📄 CSV: {OUTPUT_CSV}")
    browser.close()
