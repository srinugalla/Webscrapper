import requests
import csv
import time
import os
from datetime import datetime
from requests.exceptions import RequestException

# ================= CONFIG =================

AUTH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxODAwNDgxMzQzLCJpYXQiOjE3Njg5NDUzNDMsImp0aSI6ImI1ODllODQ2MDI0YjRiMWY4MWI4NTZmMjZhNzcwMzcwIiwidXNlcl9pZCI6MjA4MiwidG9rZW5fdmVyc2lvbiI6MSwiZGV2aWNlX3R5cGUiOiJkZXNrdG9wIiwic2Vzc2lvbl9pZCI6ImVmNDc2NTBmLWE3MTEtNDE5NS05OThlLWVjN2EzZWQ2ZTQ5ZSJ9.9rFgVTqJ8yPDIoIXJU6jEpivittpWbYH_8Mkf1OBXDI"

HEADERS = {
    "Authorization": f"Token {AUTH_TOKEN}",
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://1acre.in/",
    "Origin": "https://1acre.in"
}

LAND_URL = "https://prod-be.1acre.in/lands/"
CONTACT_URL = "https://prod-be.1acre.in/sellercontacts/"

MAX = 15000
OUTPUT_FILE = "1acre_full_export.csv"

FIELDS = [
    "land_id",
    "price_per_acre",
    "total_price",
    "area",
    "area_unit",
    "state",
    "district",
    "mandal",
    "village",
    "latitude",
    "longitude",
    "image_urls",
    "seller_name",
    "seller_type",
    "phone",
    "account_id"
]

# ================= HELPERS =================

def safe_request(method, url, **kwargs):
    for attempt in range(5):
        try:
            r = requests.request(method, url, timeout=30, **kwargs)
            if r.status_code == 200:
                return r
        except RequestException:
            wait = 2 ** attempt
            print(f"⚠️ Network error, retrying in {wait}s...")
            time.sleep(wait)
    return None


def extract_location(divs):
    loc = {"state": None, "district": None, "mandal": None, "village": None}
    for d in divs:
        if d["division_type"] == "state":
            loc["state"] = d["name"]
        elif d["division_type"] == "district":
            loc["district"] = d["name"]
        elif d["division_type"] in ("mandal", "taluk"):
            loc["mandal"] = d["name"]
        elif d["division_type"] == "village":
            loc["village"] = d["name"]
    return loc


def extract_area_unit(land_size):
    acres = land_size.get("total_land_size_in_acres") or {}
    for u in ["acres", "cents", "guntas", "grounds"]:
        if acres.get(u):
            return u
    return None


def extract_images(media):
    return " | ".join(m["image_s3"] for m in media if m.get("image_s3"))


# ================= LOAD CHECKPOINT =================

saved_ids = set()

if os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            saved_ids.add(int(r["land_id"]))

print(f"🔁 Resuming — {len(saved_ids)} records already saved")

# ================= OPEN CSV =================

file_exists = os.path.exists(OUTPUT_FILE)

csv_file = open(OUTPUT_FILE, "a", newline="", encoding="utf-8")
writer = csv.DictWriter(csv_file, fieldnames=FIELDS)

if not file_exists:
    writer.writeheader()
    csv_file.flush()

# ================= SCRAPER =================

page = 1
total_saved = len(saved_ids)

while total_saved < MAX:
    r = safe_request("GET", LAND_URL, headers=HEADERS, params={"page": page})
    if not r:
        print("❌ Failed to fetch land page, stopping safely.")
        break

    lands = r.json().get("results", [])
    if not lands:
        break

    for land in lands:
        land_id = land["id"]

        if land_id in saved_ids:
            continue

        loc = extract_location(land.get("division_info", []))

        row = {
            "land_id": land_id,
            "price_per_acre": land.get("price_per_acre"),
            "total_price": land.get("total_price"),
            "area": land.get("total_land_size"),
            "area_unit": extract_area_unit(land.get("land_size", {})),
            "state": loc["state"],
            "district": loc["district"],
            "mandal": loc["mandal"],
            "village": loc["village"],
            "latitude": land.get("lat"),
            "longitude": land.get("long"),
            "image_urls": extract_images(land.get("land_media", [])),
            "seller_name": land["seller"].get("name"),
            "seller_type": land.get("seller_type"),
            "phone": None,
            "account_id": land["seller"].get("id"),
        }

        payload = {"land": land_id, "account": row["account_id"]}
        cr = safe_request("POST", CONTACT_URL, headers=HEADERS, json=payload)

        if cr:
            row["phone"] = cr.json().get("seller_contact")

        writer.writerow(row)
        csv_file.flush()

        saved_ids.add(land_id)
        total_saved += 1

        print(f"✅ Saved {total_saved}/{MAX}")
        time.sleep(0.2)

    page += 1
    time.sleep(0.4)

csv_file.close()

print("\n🎉 SCRAPE COMPLETE")
print(f"📄 File: {OUTPUT_FILE}")
