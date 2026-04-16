# Uber Receipt Generator

A two-step Streamlit app that generates custom Uber-style receipt PDFs. Pick one of 7 real extracted trips as a template, edit any field, and download a clean A4 PDF that matches the look of genuine Uber receipts — including the UberMove font, real icons extracted from the original PDFs, and correct fare calculations.

## Features

- Template picker pre-fills all fields from 7 real extracted receipts
- Supports **Uber Go** and **Auto** fare schemas with correct GST / booking fee logic
- **Uber One** subscription badge and credits earned box
- Vehicle icon, cash / UPI payment icon, and ⊕ Uber One logo all extracted from the original PDFs
- 2-page A4 PDF: fare summary on page 1, trip route + driver on page 2
- Rendered in the official **UberMove** font (Medium + Bold)

## Project Structure

```
.
├── app.py                  — Streamlit wizard UI (2-step form + download)
├── pdf_generator.py        — ReportLab canvas-based PDF renderer
├── data_loader.py          — Reads receipt_data.json, returns template dicts
├── extract_receipts.py     — One-time script: extracts data from source PDFs
├── receipt_data.json       — Structured data for all 7 extracted receipts
├── Uber Font/
│   ├── UberMoveMedium.otf
│   └── UberMoveBold.otf
├── assets/
│   ├── fonts/              — TTF versions of UberMove (committed, ready to use)
│   ├── icons/              — Extracted brand icons: vehicle, payment, Uber One (committed)
│   └── maps/               — Extracted map PNGs (gitignored — private trip data)
└── tests/
    ├── test_pdf_generator.py
    └── test_data_loader.py
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install streamlit reportlab pdfplumber pypdf Pillow fonttools
```

All required assets (`assets/fonts/`, `assets/icons/`) are committed in the repo — no extraction step needed to run the app.

## Run

```bash
source venv/bin/activate
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Fare Calculation Rules

| Rule | Value |
|---|---|
| Uber Go total | trip_charge + ₹3.00 insurance |
| Auto total | suggested_fare + ₹1.00 booking fee + ₹3.00 insurance |
| GST (Uber Go only) | 7.07% back-calculated from trip_charge (already included) |
| Insurance | ₹3.00 (fixed, both types) |
| Booking fee (Auto only) | ₹1.00 (fixed) |

## Re-extracting Receipt Data

Place source PDFs in the project root and run:

```bash
python extract_receipts.py
```

This overwrites `receipt_data.json` and refreshes `assets/maps/`.

## Tests

```bash
pytest tests/ -v
```

13 tests covering fare calculations, data loading, and PDF generation.
