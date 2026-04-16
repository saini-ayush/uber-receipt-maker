# Streamlit Uber Receipt Generator — Design Spec

**Date:** 2026-04-16  
**Status:** Approved

---

## Overview

A two-step Streamlit web app that lets the user generate custom Uber-style receipt PDFs on demand. The user either starts from scratch or picks one of 7 extracted real receipts as a template. Every field is editable. The app produces a clean, professional single-page PDF (no map image).

---

## Architecture

```
Guddu-uber-recp/
├── app.py                ← Streamlit wizard (UI only, no PDF logic)
├── pdf_generator.py      ← ReportLab receipt renderer (no Streamlit imports)
├── data_loader.py        ← Reads receipt_data.json, returns template dicts
├── receipt_data.json     ← Existing extracted receipt data (7 receipts)
├── assets/maps/          ← Existing map PNGs (not used in PDF output)
└── venv/
```

**Data flow:**

1. `data_loader.py` reads `receipt_data.json` on app start and returns a list of template dicts.
2. `app.py` manages wizard state via `st.session_state` (`step = 1 | 2`, `form_data = dict`).
3. On Step 2, user clicks "Generate Receipt PDF" → `app.py` calls `pdf_generator.generate(form_data)` → returns `bytes`.
4. Streamlit's `st.download_button` streams the bytes to the browser. No temp files written to disk.

---

## Step 1 — Template Picker + Form

### Template Picker

- Dropdown at the top: "Start from scratch" or one of 7 receipt names.
- Selecting a template pre-fills all form fields below.

### Form Groups

**Trip Info**

- Date (date input)
- Booking time (time input)
- Rider name (text input)
- Vehicle type: `Uber Go` | `Auto` (select box — controls which fare schema appears)
- License plate (text input)

**Route**

- Pickup time (time input) + Pickup address (text area)
- Dropoff time (time input) + Dropoff address (text area)
- Distance in km (number input)
- Duration in minutes (number input)

**Fare** (schema switches on vehicle type)

| Vehicle Type | Fields                                                                                                                                                                                    |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Uber Go      | Trip charge (user enters the gross amount, GST already inside) → GST back-calc (trip_charge × 7.07%) shown read-only → Insurance fixed ₹3.00 → Total = trip_charge + insurance, read-only |
| Auto         | Suggested fare → Booking fee fixed ₹1.00 → Insurance fixed ₹3.00 → Total read-only (no GST)                                                                                               |

- Uber One credits earned (optional, number input, default 0)
- Payment method: `Cash` | `UPI Scan and Pay` (select box)
- Payment timestamp (text input, e.g. "4/10/26 1:54 pm")

**Driver**

- Driver name (text input): Give random Indian names as choice
- Driver rating (slider 0.0–5.0, step 0.01)

### Navigation

- "Next: Preview Receipt →" button — disabled until required fields are non-empty: date, pickup address, dropoff address, base fare > 0, rider name, driver name.

---

## Step 2 — Preview + Download

**Layout:** Two columns.

- **Left column (narrow):** Summary card — all key values listed for a quick sanity check. "← Back" button returns to Step 1 with form data preserved.
- **Right column (wide):** "Generate Receipt PDF" button. On click: generates PDF in-memory, shows `st.download_button` + success message with filename (e.g. `receipt_Hotel_1_to_Pallaruthy.pdf`).

---

## PDF Layout (ReportLab)

**Page:** A4, portrait, single page.  
**Font:** Helvetica (built-in, no external files required).  
**Dividers:** Light grey horizontal rules between sections.

Four sections top-to-bottom:

1. **Header** — Bold "Uber" wordmark left-aligned. Receipt date + booking time right-aligned.
2. **Fare Summary** — Greeting: "Thanks for riding, [Rider Name]". Two-column table:
   - Uber Go rows: Trip charge, Insurance, GST included (italic note), **Total** (bold)
   - Auto rows: Suggested fare, Booking fee, Insurance, **Total** (bold, no GST row)
   - Uber One credits earned row (only if > 0)
   - Payment method + timestamp below table.
3. **Trip Details** — Pickup pin (●) with time + address. Dropoff pin (●) with time + address. Below: distance, duration, vehicle type, license plate.
4. **Driver Footer** — "You rode with [Driver Name] ★ [Rating]" centered.

---

## Fare Calculation Rules

| Rule                    | Value                                                                                     |
| ----------------------- | ----------------------------------------------------------------------------------------- |
| GST rate (Uber Go only) | 7.07% of trip_charge (back-calculated; matches extracted receipts; configurable constant) |
| Insurance               | ₹3.00 (fixed, both types)                                                                 |
| Booking fee (Auto only) | ₹1.00 (fixed)                                                                             |
| Uber Go total           | trip_charge + insurance                                                                   |
| Auto total              | suggested_fare + booking_fee + insurance                                                  |
| GST display (Uber Go)   | Shown as "The total of ₹X has a GST of ₹Y included." note below fare table                |

---

## Dependencies

All installed in existing venv:

- `streamlit` (needs `pip install streamlit`)
- `reportlab` (needs `pip install reportlab`)
- `pdfplumber`, `pypdf`, `Pillow` (already installed)

---

## Out of Scope

- Map image embedding in PDF
- Pixel-perfect Uber branding / fonts
- Multi-page receipts
- Saving generated receipts back to `receipt_data.json`
- Authentication or multi-user support
