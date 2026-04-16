"""
Uber Receipt PDF Extractor
Parses all Uber receipt PDFs, extracts structured data, extracts map images,
and saves everything to receipt_data.json.
"""

import os
import re
import json
import pdfplumber
from pypdf import PdfReader
from pdf2image import convert_from_path
from PIL import Image
import io

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAPS_DIR = os.path.join(BASE_DIR, "assets", "maps")
os.makedirs(MAPS_DIR, exist_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def clean(s):
    """Strip extra whitespace."""
    return re.sub(r"\s+", " ", s).strip() if s else s


def parse_amount(s):
    """'₹199.95' → 199.95"""
    if s is None:
        return None
    m = re.search(r"[\d,]+\.?\d*", s.replace(",", ""))
    return float(m.group()) if m else None


def parse_distance_time(text):
    """'6.95 kilometres, 18 minutes' → (6.95, 18)"""
    m = re.search(r"([\d.]+)\s+kilometres?,\s+(\d+)\s+minutes?", text)
    if m:
        return float(m.group(1)), int(m.group(2))
    return None, None


# ──────────────────────────────────────────────────────────────────────────────
# Page-1 parser (fare summary)
# ──────────────────────────────────────────────────────────────────────────────

def parse_page1(text):
    data = {}

    # Date / time header  e.g. "Apr 10, 2026\n1:30 pm"
    date_m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}", text)
    time_m = re.search(r"^(\d{1,2}:\d{2}\s*[ap]m)", text, re.MULTILINE)
    data["receipt_date"] = date_m.group() if date_m else None
    data["receipt_time"] = time_m.group(1).strip() if time_m else None

    # Rider name
    rider_m = re.search(r"Thanks for riding,\s+(.+)", text)
    data["rider_name"] = clean(rider_m.group(1)) if rider_m else None

    # Totals
    total_m = re.search(r"Total\s+₹([\d.]+)", text)
    data["total_fare"] = float(total_m.group(1)) if total_m else None

    # --- charge lines ---
    # Uber Go / Moto: "Trip charge ₹X"
    trip_charge_m = re.search(r"Trip charge\s+₹([\d.]+)", text)
    data["trip_charge"] = float(trip_charge_m.group(1)) if trip_charge_m else None

    # Auto: "Suggested fare ₹X"
    sug_m = re.search(r"Suggested fare\s+₹([\d.]+)", text)
    data["suggested_fare"] = float(sug_m.group(1)) if sug_m else None

    # Booking fee (Auto trips)
    booking_m = re.search(r"Booking fee\s+₹([\d.]+)", text)
    data["booking_fee"] = float(booking_m.group(1)) if booking_m else None

    # Insurance
    ins_m = re.search(r"Insurance\s+₹([\d.]+)", text)
    data["insurance"] = float(ins_m.group(1)) if ins_m else None

    # GST
    gst_m = re.search(r"has a GST of\s+₹([\d.]+)\s+included", text)
    data["gst_included"] = float(gst_m.group(1)) if gst_m else None

    # Uber One credits
    credits_m = re.search(r"₹([\d.]+)\s*\n?\s*Uber One credits earned", text)
    data["uber_one_credits_earned"] = float(credits_m.group(1)) if credits_m else None

    # Payments block — collect all payment lines
    payments = []
    # "Cash ₹199.95\n4/10/26 1:54 pm"  or  "UPI Scan and Pay ₹189.96\n4/15/26 2:07 pm"
    for m in re.finditer(
        r"(Cash|UPI Scan and Pay|Credit Card|Debit Card|Paytm|Google Pay|PhonePe)\s+₹([\d.]+)\s*\n?([\d/]+\s+[\d:]+\s*[ap]m)?(\s*Failed)?",
        text
    ):
        entry = {
            "method": m.group(1),
            "amount": float(m.group(2)),
            "timestamp": clean(m.group(3)) if m.group(3) else None,
            "status": "Failed" if m.group(4) and "Failed" in m.group(4) else "Success",
        }
        payments.append(entry)
    data["payments"] = payments

    # Vehicle type + license plate
    # Uber Go: "Uber Go License Plate:\n6.95 kilometres … KL47N0640"
    # Auto: "Auto License Plate:\n6.06 kilometres … KL07DF8963"
    veh_m = re.search(r"(Uber Go|Auto|Uber Moto|Uber Premier|UberX)\s+License Plate:", text)
    data["vehicle_type"] = veh_m.group(1) if veh_m else None

    # License plate: all-caps 2-letter state code + digits/letters, e.g. KL47N0640
    plate_m = re.search(r"\b(KL\w{6,8})\b", text)
    data["license_plate"] = plate_m.group(1) if plate_m else None

    # Distance / duration
    dist, dur = parse_distance_time(text)
    data["distance_km"] = dist
    data["duration_min"] = dur

    return data


# ──────────────────────────────────────────────────────────────────────────────
# Page-2 parser (trip locations + driver)
# ──────────────────────────────────────────────────────────────────────────────

def parse_page2(text, page1_data):
    data = {}

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # If vehicle type / license plate appear on page 2 instead of page 1
    if not page1_data.get("vehicle_type"):
        veh_m = re.search(r"(Uber Go|Auto|Uber Moto|Uber Premier|UberX)\s+License Plate:", text)
        if veh_m:
            page1_data["vehicle_type"] = veh_m.group(1)
    if not page1_data.get("license_plate"):
        plate_m = re.search(r"\b(KL\w{6,8})\b", text)
        if plate_m:
            page1_data["license_plate"] = plate_m.group(1)
    if not page1_data.get("distance_km"):
        dist, dur = parse_distance_time(text)
        page1_data["distance_km"] = dist
        page1_data["duration_min"] = dur

    # Time stamps: "1:35 pm" lines
    time_pattern = re.compile(r"^\d{1,2}:\d{2}\s*[ap]m$", re.IGNORECASE)
    time_indices = [i for i, l in enumerate(lines) if time_pattern.match(l)]

    if len(time_indices) >= 2:
        pickup_time_idx = time_indices[0]
        dropoff_time_idx = time_indices[1]

        # Address: everything between this time and the next time (or driver line)
        # Pickup address
        pickup_addr_lines = []
        for l in lines[pickup_time_idx + 1 : dropoff_time_idx]:
            if re.match(r"You rode with", l):
                break
            pickup_addr_lines.append(l)
        data["pickup_time"] = lines[pickup_time_idx]
        data["pickup_address"] = clean(" ".join(pickup_addr_lines))

        # Dropoff address: from dropoff_time onward until driver line
        dropoff_addr_lines = []
        for l in lines[dropoff_time_idx + 1 :]:
            if re.match(r"You rode with", l):
                break
            dropoff_addr_lines.append(l)
        data["dropoff_time"] = lines[dropoff_time_idx]
        data["dropoff_address"] = clean(" ".join(dropoff_addr_lines))
    else:
        data["pickup_time"] = None
        data["pickup_address"] = None
        data["dropoff_time"] = None
        data["dropoff_address"] = None

    # Driver + rating  "You rode with Mohammed Rinas 4.94"
    driver_m = re.search(r"You rode with\s+(.+?)\s+([\d.]+)$", text, re.MULTILINE)
    if driver_m:
        data["driver_name"] = clean(driver_m.group(1))
        data["driver_rating"] = float(driver_m.group(2))
    else:
        data["driver_name"] = None
        data["driver_rating"] = None

    return data


# ──────────────────────────────────────────────────────────────────────────────
# Map image extractor  (uses pypdf + PIL to pull the large ~262×268 image)
# ──────────────────────────────────────────────────────────────────────────────

def extract_map_image(pdf_path, receipt_id):
    """
    Extracts the largest embedded image from the PDF (the map) and saves it
    to assets/maps/<receipt_id>.png.  Returns the relative path or None.
    """
    try:
        reader = PdfReader(pdf_path)
        best_img_data = None
        best_size = 0

        for page in reader.pages:
            if "/Resources" not in page:
                continue
            resources = page["/Resources"]
            xobjects = resources.get("/XObject")
            if not xobjects:
                continue
            for obj_name in xobjects:
                obj = xobjects[obj_name]
                if obj.get("/Subtype") == "/Image":
                    width = obj.get("/Width", 0)
                    height = obj.get("/Height", 0)
                    size = width * height
                    if size > best_size:
                        best_size = size
                        best_img_data = obj

        if best_img_data is None:
            return None

        raw = best_img_data.get_data()
        cs = best_img_data.get("/ColorSpace")
        w = int(best_img_data["/Width"])
        h = int(best_img_data["/Height"])

        # Try to open as JPEG first (most common for maps)
        try:
            img = Image.open(io.BytesIO(raw))
        except Exception:
            # Fall back to raw RGB
            mode = "RGB" if cs == "/DeviceRGB" else "L"
            img = Image.frombytes(mode, (w, h), raw)

        out_path = os.path.join(MAPS_DIR, f"{receipt_id}.png")
        img.save(out_path, "PNG")
        return os.path.join("assets", "maps", f"{receipt_id}.png")

    except Exception as e:
        print(f"  [WARN] Could not extract map from {os.path.basename(pdf_path)}: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def process_pdf(pdf_path):
    filename = os.path.basename(pdf_path)
    receipt_id = os.path.splitext(filename)[0].replace(" ", "_")
    print(f"Processing: {filename}")

    with pdfplumber.open(pdf_path) as pdf:
        page1_text = pdf.pages[0].extract_text() or ""
        page2_text = pdf.pages[1].extract_text() if len(pdf.pages) > 1 else ""

    page1_data = parse_page1(page1_text)
    page2_data = parse_page2(page2_text, page1_data)  # may update page1_data in-place

    map_path = extract_map_image(pdf_path, receipt_id)
    print(f"  Map saved: {map_path}")

    record = {
        "receipt_id": receipt_id,
        "source_file": filename,
        # ── Booking header ──
        "receipt_date": page1_data.get("receipt_date"),
        "receipt_time": page1_data.get("receipt_time"),
        "rider_name": page1_data.get("rider_name"),
        # ── Trip details ──
        "vehicle_type": page1_data.get("vehicle_type"),
        "license_plate": page1_data.get("license_plate"),
        "distance_km": page1_data.get("distance_km"),
        "duration_min": page1_data.get("duration_min"),
        # ── Route ──
        "pickup": {
            "time": page2_data.get("pickup_time"),
            "address": page2_data.get("pickup_address"),
        },
        "dropoff": {
            "time": page2_data.get("dropoff_time"),
            "address": page2_data.get("dropoff_address"),
        },
        # ── Fare breakdown ──
        "fare": {
            "total": page1_data.get("total_fare"),
            "trip_charge": page1_data.get("trip_charge"),          # Uber Go trips
            "suggested_fare": page1_data.get("suggested_fare"),    # Auto trips
            "booking_fee": page1_data.get("booking_fee"),          # Auto trips
            "insurance": page1_data.get("insurance"),
            "gst_included": page1_data.get("gst_included"),
            "uber_one_credits_earned": page1_data.get("uber_one_credits_earned"),
        },
        # ── Payments ──
        "payments": page1_data.get("payments", []),
        # ── Driver ──
        "driver": {
            "name": page2_data.get("driver_name"),
            "rating": page2_data.get("driver_rating"),
        },
        # ── Assets ──
        "map_image": map_path,
    }
    return record


def main():
    pdf_files = sorted([
        os.path.join(BASE_DIR, f)
        for f in os.listdir(BASE_DIR)
        if f.endswith(".pdf")
    ])

    receipts = []
    for pdf_path in pdf_files:
        try:
            record = process_pdf(pdf_path)
            receipts.append(record)
        except Exception as e:
            print(f"  [ERROR] {os.path.basename(pdf_path)}: {e}")

    output = {
        "schema_version": "1.0",
        "description": "Extracted Uber receipt data — usable as a template schema for generating custom receipts",
        "template_fields": {
            "receipt_id":    "Unique identifier derived from filename",
            "source_file":   "Original PDF filename",
            "receipt_date":  "Date shown at top of receipt  (e.g. 'Apr 10, 2026')",
            "receipt_time":  "Booking request time  (e.g. '1:30 pm')",
            "rider_name":    "Name of the rider",
            "vehicle_type":  "Service tier: 'Uber Go' | 'Auto' | 'Uber Moto' | ...",
            "license_plate": "Vehicle registration number",
            "distance_km":   "Trip distance in kilometres",
            "duration_min":  "Trip duration in minutes",
            "pickup":        "{ time, address }",
            "dropoff":       "{ time, address }",
            "fare": {
                "total":                   "Grand total charged",
                "trip_charge":             "Base fare for Uber Go / cab trips (incl. GST)",
                "suggested_fare":          "Base fare for Auto trips (excl. GST)",
                "booking_fee":             "Platform booking fee (Auto trips)",
                "insurance":               "Compulsory insurance component",
                "gst_included":            "GST amount embedded in trip_charge (Uber Go only)",
                "uber_one_credits_earned": "Loyalty credits earned (if applicable)",
            },
            "payments":      "List of { method, amount, timestamp, status }",
            "driver":        "{ name, rating }",
            "map_image":     "Relative path to extracted map PNG in assets/maps/",
        },
        "receipts": receipts,
    }

    out_path = os.path.join(BASE_DIR, "receipt_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {len(receipts)} receipts saved → {out_path}")
    return output


if __name__ == "__main__":
    main()
