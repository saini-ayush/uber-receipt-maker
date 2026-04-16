# Streamlit Uber Receipt Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-step Streamlit app that generates custom Uber receipt PDFs on demand, pre-filled from any of 7 extracted real receipts.

**Architecture:** Three focused modules — `data_loader.py` (reads `receipt_data.json`), `pdf_generator.py` (ReportLab renderer, no Streamlit), `app.py` (Streamlit wizard, no PDF logic). PDF bytes are generated in-memory and streamed via `st.download_button`. Wizard state lives in `st.session_state`.

**Tech Stack:** Python 3.12, Streamlit, ReportLab, pypdf (already installed), pytest.

---

## File Map

| File | Responsibility |
|---|---|
| `data_loader.py` | Load `receipt_data.json`, return template list and lookups |
| `pdf_generator.py` | Fare calculation helpers + `generate(form_data) → bytes` |
| `app.py` | Streamlit wizard: `_init_state()`, `_step1()`, `_step2()`, `main()` |
| `tests/test_data_loader.py` | Unit tests for data_loader |
| `tests/test_pdf_generator.py` | Unit tests for fare helpers and `generate()` |

---

## Task 1: Install Dependencies

**Files:**
- Create: `tests/__init__.py` (already done)

- [ ] **Step 1: Install streamlit and reportlab**

```bash
source venv/bin/activate && pip install streamlit reportlab
```

Expected output ends with: `Successfully installed ...reportlab... streamlit...`

- [ ] **Step 2: Verify imports**

```bash
source venv/bin/activate && python3 -c "import streamlit; import reportlab; print('OK')"
```

Expected: `OK`

---

## Task 2: data_loader.py

**Files:**
- Create: `tests/test_data_loader.py`
- Create: `data_loader.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_data_loader.py`:

```python
import data_loader


def test_load_templates_returns_seven():
    assert len(data_loader.load_templates()) == 7


def test_templates_have_required_keys():
    required = {"receipt_id", "receipt_date", "rider_name", "vehicle_type",
                "fare", "driver", "pickup", "dropoff"}
    for t in data_loader.load_templates():
        assert required.issubset(t.keys()), f"Missing keys in {t['receipt_id']}"


def test_display_names_are_strings():
    names = data_loader.template_display_names()
    assert len(names) == 7
    assert all(isinstance(n, str) for n in names)


def test_template_by_index_round_trips():
    templates = data_loader.load_templates()
    for i, t in enumerate(templates):
        assert data_loader.template_by_index(i)["receipt_id"] == t["receipt_id"]
```

- [ ] **Step 2: Run — verify they fail**

```bash
source venv/bin/activate && python3 -m pytest tests/test_data_loader.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'data_loader'`

- [ ] **Step 3: Implement data_loader.py**

Create `data_loader.py`:

```python
import json
import os
from typing import Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECEIPT_DATA_PATH = os.path.join(BASE_DIR, "receipt_data.json")


def load_templates() -> list[dict[str, Any]]:
    with open(RECEIPT_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["receipts"]


def template_display_names() -> list[str]:
    return [t["receipt_id"].replace("_", " ") for t in load_templates()]


def template_by_index(index: int) -> dict[str, Any]:
    return load_templates()[index]
```

- [ ] **Step 4: Run — verify they pass**

```bash
source venv/bin/activate && python3 -m pytest tests/test_data_loader.py -v
```

Expected: `4 passed`

---

## Task 3: pdf_generator.py — Fare Helpers

**Files:**
- Create: `tests/test_pdf_generator.py`
- Create: `pdf_generator.py` (fare helpers only)

- [ ] **Step 1: Write failing tests for fare helpers**

Create `tests/test_pdf_generator.py`:

```python
import pdf_generator


def test_calc_gst_on_known_receipt():
    # Hotel 1 to Pallaruthy: trip_charge=196.95, real GST=13.91
    gst = pdf_generator.calc_gst(196.95)
    assert abs(gst - 13.91) < 0.50  # within 50 paise

def test_uber_go_total():
    # trip_charge=196.95, insurance=3.00 → total=199.95
    assert pdf_generator.uber_go_total(196.95) == 199.95

def test_auto_total():
    # suggested_fare=97.05, booking_fee=1.00, insurance=3.00 → total=101.05
    assert pdf_generator.auto_total(97.05) == 101.05

def test_uber_go_total_with_zero():
    assert pdf_generator.uber_go_total(0.0) == 3.0

def test_auto_total_with_zero():
    assert pdf_generator.auto_total(0.0) == 4.0
```

- [ ] **Step 2: Run — verify they fail**

```bash
source venv/bin/activate && python3 -m pytest tests/test_pdf_generator.py -v 2>&1 | head -15
```

Expected: `ModuleNotFoundError: No module named 'pdf_generator'`

- [ ] **Step 3: Implement fare helpers in pdf_generator.py**

Create `pdf_generator.py`:

```python
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

# ~7.07% back-calculated from all 7 extracted receipts (configurable)
GST_RATE = 0.0707
INSURANCE = 3.00
BOOKING_FEE = 1.00


def calc_gst(trip_charge: float) -> float:
    """Back-calculate GST from gross trip charge (Uber Go only)."""
    return round(trip_charge * GST_RATE, 2)


def uber_go_total(trip_charge: float) -> float:
    return round(trip_charge + INSURANCE, 2)


def auto_total(suggested_fare: float) -> float:
    return round(suggested_fare + BOOKING_FEE + INSURANCE, 2)
```

- [ ] **Step 4: Run — verify they pass**

```bash
source venv/bin/activate && python3 -m pytest tests/test_pdf_generator.py -v
```

Expected: `5 passed`

---

## Task 4: pdf_generator.py — generate()

**Files:**
- Modify: `pdf_generator.py` (add `_build_styles()` and `generate()`)
- Modify: `tests/test_pdf_generator.py` (add PDF output tests)

- [ ] **Step 1: Add failing tests for generate()**

Append the following to the **top** of `tests/test_pdf_generator.py` (add imports after the existing `import pdf_generator` line):

```python
from pypdf import PdfReader
import io


UBER_GO_FORM = {
    "receipt_date": "Apr 10, 2026",
    "receipt_time": "1:30 pm",
    "rider_name": "Dyrus",
    "vehicle_type": "Uber Go",
    "license_plate": "KL47N0640",
    "distance_km": 6.95,
    "duration_min": 18,
    "pickup_time": "1:35 pm",
    "pickup_address": "W7J9+FFX, Baby Marine Rd, Thoppumpady, Kochi",
    "dropoff_time": "1:54 pm",
    "dropoff_address": "2011 M.G Road, Shenoys, Kochi",
    "vehicle_type": "Uber Go",
    "trip_charge": 196.95,
    "suggested_fare": None,
    "uber_one_credits": 0.0,
    "total": 199.95,
    "payment_method": "Cash",
    "payment_timestamp": "4/10/26 1:54 pm",
    "driver_name": "Mohammed Rinas",
    "driver_rating": 4.94,
}

AUTO_FORM = {**UBER_GO_FORM,
    "vehicle_type": "Auto",
    "trip_charge": None,
    "suggested_fare": 97.05,
    "total": 101.05,
    "license_plate": "KL41N5080",
}


def test_generate_returns_pdf_bytes():
    result = pdf_generator.generate(UBER_GO_FORM)
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


def test_generate_uber_go_contains_rider_name():
    pdf_bytes = pdf_generator.generate(UBER_GO_FORM)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "".join(p.extract_text() for p in reader.pages)
    assert "Dyrus" in text
    assert "Mohammed Rinas" in text


def test_generate_auto_does_not_have_trip_charge_label():
    pdf_bytes = pdf_generator.generate(AUTO_FORM)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "".join(p.extract_text() for p in reader.pages)
    assert "Suggested fare" in text
    assert "Trip charge" not in text


def test_generate_uber_go_includes_gst_note():
    pdf_bytes = pdf_generator.generate(UBER_GO_FORM)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "".join(p.extract_text() for p in reader.pages)
    assert "GST" in text
```

- [ ] **Step 2: Run — verify they fail**

```bash
source venv/bin/activate && python3 -m pytest tests/test_pdf_generator.py::test_generate_returns_pdf_bytes -v
```

Expected: `AttributeError: module 'pdf_generator' has no attribute 'generate'`

- [ ] **Step 3: Implement _build_styles() and generate() in pdf_generator.py**

Append to `pdf_generator.py` (after the fare helpers):

```python
def _build_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "uber_title":      ParagraphStyle("uber_title",    parent=base["Normal"],
                                           fontSize=22, fontName="Helvetica-Bold"),
        "right":           ParagraphStyle("right",         parent=base["Normal"],
                                           alignment=TA_RIGHT, fontSize=10),
        "greeting":        ParagraphStyle("greeting",      parent=base["Normal"],
                                           fontSize=13, fontName="Helvetica-Bold"),
        "section_header":  ParagraphStyle("sec_hdr",       parent=base["Normal"],
                                           fontSize=10, fontName="Helvetica-Bold"),
        "normal":          ParagraphStyle("normal_body",   parent=base["Normal"],
                                           fontSize=10),
        "small":           ParagraphStyle("small_body",    parent=base["Normal"],
                                           fontSize=8, textColor=colors.grey),
        "small_italic":    ParagraphStyle("small_italic",  parent=base["Normal"],
                                           fontSize=8, textColor=colors.grey,
                                           fontName="Helvetica-Oblique"),
        "bold_small":      ParagraphStyle("bold_small",    parent=base["Normal"],
                                           fontSize=10, fontName="Helvetica-Bold"),
        "centered":        ParagraphStyle("centered",      parent=base["Normal"],
                                           alignment=TA_CENTER, fontSize=10),
        "total_bold":      ParagraphStyle("total_bold",    parent=base["Normal"],
                                           fontSize=11, fontName="Helvetica-Bold"),
    }


def generate(form_data: dict) -> bytes:
    """Render a receipt PDF and return as bytes. No files written to disk."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20 * mm, leftMargin=20 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm)
    s = _build_styles()
    story = []

    # ── 1. Header ─────────────────────────────────────────────────────────
    header = Table(
        [[Paragraph("Uber", s["uber_title"]),
          Paragraph(f"{form_data['receipt_date']}&nbsp;&nbsp;{form_data['receipt_time']}",
                    s["right"])]],
        colWidths=["60%", "40%"],
    )
    story += [header, Spacer(1, 3 * mm),
              HRFlowable(width="100%", thickness=1, color=colors.lightgrey),
              Spacer(1, 5 * mm)]

    # ── 2. Fare Summary ───────────────────────────────────────────────────
    vtype = form_data["vehicle_type"]
    total = form_data["total"]

    story.append(Paragraph(f"Thanks for riding, {form_data['rider_name']}", s["greeting"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Total &nbsp; &#8377;{total:.2f}", s["total_bold"]))
    story.append(Spacer(1, 3 * mm))

    # Fare breakdown table
    fare_rows = []
    if vtype == "Uber Go":
        fare_rows.append(["Trip charge", f"\u20b9{form_data['trip_charge']:.2f}"])
    else:
        fare_rows.append(["Suggested fare", f"\u20b9{form_data['suggested_fare']:.2f}"])
        fare_rows.append(["Booking fee",    f"\u20b9{BOOKING_FEE:.2f}"])
    fare_rows.append(["Insurance", f"\u20b9{INSURANCE:.2f}"])
    credits = form_data.get("uber_one_credits") or 0
    if credits > 0:
        fare_rows.append([f"\u20b9{credits:.2f}", "Uber One credits earned"])

    fare_table = Table(fare_rows, colWidths=["70%", "30%"])
    fare_table.setStyle(TableStyle([
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("ALIGN",         (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TEXTCOLOR",     (0, 0), (-1, -1), colors.black),
    ]))
    story.append(fare_table)
    story.append(Spacer(1, 4 * mm))

    # Payments
    story.append(Paragraph("Payments", s["section_header"]))
    story.append(Paragraph(
        f"{form_data['payment_method']} &nbsp; \u20b9{total:.2f}", s["normal"]))
    if form_data.get("payment_timestamp"):
        story.append(Paragraph(form_data["payment_timestamp"], s["small"]))

    # GST note (Uber Go only)
    if vtype == "Uber Go":
        gst = calc_gst(form_data["trip_charge"])
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            f"The total of \u20b9{total:.2f} has a GST of \u20b9{gst:.2f} included.",
            s["small_italic"]))

    story += [Spacer(1, 5 * mm),
              HRFlowable(width="100%", thickness=1, color=colors.lightgrey),
              Spacer(1, 5 * mm)]

    # ── 3. Trip Details ───────────────────────────────────────────────────
    story.append(Paragraph("Trip details", s["section_header"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(f"\u25cf &nbsp; {form_data['pickup_time']}", s["bold_small"]))
    story.append(Paragraph(form_data["pickup_address"], s["normal"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"\u25cf &nbsp; {form_data['dropoff_time']}", s["bold_small"]))
    story.append(Paragraph(form_data["dropoff_address"], s["normal"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"{form_data['distance_km']} kilometres, {form_data['duration_min']} minutes"
        f" &nbsp;\u2022&nbsp; {vtype} &nbsp;\u2022&nbsp; {form_data['license_plate']}",
        s["small"]))

    story += [Spacer(1, 5 * mm),
              HRFlowable(width="100%", thickness=1, color=colors.lightgrey),
              Spacer(1, 5 * mm)]

    # ── 4. Driver Footer ──────────────────────────────────────────────────
    story.append(Paragraph(
        f"You rode with {form_data['driver_name']} &nbsp; \u2605 {form_data['driver_rating']}",
        s["centered"]))

    doc.build(story)
    return buffer.getvalue()
```

- [ ] **Step 4: Run all pdf_generator tests**

```bash
source venv/bin/activate && python3 -m pytest tests/test_pdf_generator.py -v
```

Expected: `9 passed`

---

## Task 5: app.py — State + Step 1

**Files:**
- Create: `app.py`

- [ ] **Step 1: Create app.py with state init, prefill logic, and Step 1 form**

Create `app.py`:

```python
import streamlit as st
from datetime import date, time as dtime
import data_loader
import pdf_generator

INDIAN_DRIVER_NAMES = [
    "Mohammed Rinas", "Nidhin", "Soniya", "Chandran",
    "Jobi P. Jacob", "Ajas", "Prajeesh N.K", "Rajesh Kumar",
    "Suresh Babu", "Priya Nair", "Anoop George", "Deepak Menon",
    "(Enter custom name)",
]


def _init_state():
    defaults = {
        "step": 1,
        "form_data": {},
        "receipt_date": date.today(),
        "receipt_time": dtime(12, 0),
        "rider_name": "",
        "vehicle_type": "Uber Go",
        "license_plate": "",
        "pickup_time": dtime(12, 0),
        "pickup_address": "",
        "dropoff_time": dtime(12, 30),
        "dropoff_address": "",
        "distance_km": 5.0,
        "duration_min": 15,
        "trip_charge": 150.0,
        "suggested_fare": 130.0,
        "uber_one_credits": 0.0,
        "payment_method": "Cash",
        "payment_timestamp": "",
        "driver_name_select": INDIAN_DRIVER_NAMES[0],
        "driver_name_custom": "",
        "driver_rating": 4.90,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _prefill_from_template(t: dict):
    """Overwrite all form session-state keys from a template dict."""
    from datetime import datetime

    def parse_time(raw: str):
        for fmt in ("%I:%M %p", "%I:%M%p"):
            try:
                return datetime.strptime(raw.strip(), fmt).time()
            except Exception:
                pass
        return dtime(12, 0)

    try:
        st.session_state.receipt_date = datetime.strptime(
            t["receipt_date"], "%b %d, %Y").date()
    except Exception:
        pass

    if t.get("receipt_time"):
        st.session_state.receipt_time = parse_time(t["receipt_time"])

    st.session_state.rider_name     = t.get("rider_name") or ""
    st.session_state.vehicle_type   = t.get("vehicle_type") or "Uber Go"
    st.session_state.license_plate  = t.get("license_plate") or ""

    pickup  = t.get("pickup")  or {}
    dropoff = t.get("dropoff") or {}
    if pickup.get("time"):
        st.session_state.pickup_time = parse_time(pickup["time"])
    st.session_state.pickup_address  = pickup.get("address") or ""
    if dropoff.get("time"):
        st.session_state.dropoff_time = parse_time(dropoff["time"])
    st.session_state.dropoff_address = dropoff.get("address") or ""

    st.session_state.distance_km  = t.get("distance_km")  or 5.0
    st.session_state.duration_min = t.get("duration_min") or 15

    fare = t.get("fare") or {}
    st.session_state.trip_charge      = fare.get("trip_charge")          or 150.0
    st.session_state.suggested_fare   = fare.get("suggested_fare")       or 130.0
    st.session_state.uber_one_credits = fare.get("uber_one_credits_earned") or 0.0

    payments = t.get("payments") or []
    if payments:
        p = payments[0]
        st.session_state.payment_method    = p.get("method")    or "Cash"
        st.session_state.payment_timestamp = p.get("timestamp") or ""

    driver = t.get("driver") or {}
    dname  = driver.get("name") or ""
    if dname in INDIAN_DRIVER_NAMES:
        st.session_state.driver_name_select = dname
        st.session_state.driver_name_custom = ""
    else:
        st.session_state.driver_name_select = "(Enter custom name)"
        st.session_state.driver_name_custom = dname
    st.session_state.driver_rating = driver.get("rating") or 4.90


def _collect_form_data() -> dict:
    ss = st.session_state
    driver_name = (
        ss.driver_name_custom
        if ss.driver_name_select == "(Enter custom name)"
        else ss.driver_name_select
    )
    vtype = ss.vehicle_type
    if vtype == "Uber Go":
        trip_charge   = ss.trip_charge
        suggested_fare = None
        total = pdf_generator.uber_go_total(trip_charge)
    else:
        trip_charge   = None
        suggested_fare = ss.suggested_fare
        total = pdf_generator.auto_total(suggested_fare)

    def fmt_time(t):
        h = t.hour % 12 or 12
        return f"{h}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"

    return {
        "receipt_date":      ss.receipt_date.strftime("%b %-d, %Y"),
        "receipt_time":      fmt_time(ss.receipt_time),
        "rider_name":        ss.rider_name,
        "vehicle_type":      vtype,
        "license_plate":     ss.license_plate,
        "distance_km":       ss.distance_km,
        "duration_min":      ss.duration_min,
        "pickup_time":       fmt_time(ss.pickup_time),
        "pickup_address":    ss.pickup_address,
        "dropoff_time":      fmt_time(ss.dropoff_time),
        "dropoff_address":   ss.dropoff_address,
        "trip_charge":       trip_charge,
        "suggested_fare":    suggested_fare,
        "uber_one_credits":  ss.uber_one_credits,
        "total":             total,
        "payment_method":    ss.payment_method,
        "payment_timestamp": ss.payment_timestamp,
        "driver_name":       driver_name,
        "driver_rating":     ss.driver_rating,
    }


def _step1():
    st.title("\U0001f697  Uber Receipt Generator")
    st.markdown("### Step 1 of 2 — Fill in Receipt Details")

    # Template picker
    template_names = ["— Start from scratch —"] + data_loader.template_display_names()

    def _on_template_change():
        sel = st.session_state.template_picker
        if sel != "— Start from scratch —":
            idx = template_names.index(sel) - 1
            _prefill_from_template(data_loader.template_by_index(idx))

    st.selectbox("Use an existing receipt as template",
                 template_names, key="template_picker",
                 on_change=_on_template_change)
    st.divider()

    # ── Trip Info ────────────────────────────────────────────────────────
    st.subheader("Trip Info")
    c1, c2 = st.columns(2)
    with c1:
        st.date_input("Date", key="receipt_date")
        st.text_input("Rider Name", key="rider_name", placeholder="e.g. Dyrus")
    with c2:
        st.time_input("Booking Time", key="receipt_time", step=60)
        st.selectbox("Vehicle Type", ["Uber Go", "Auto"], key="vehicle_type")
    st.text_input("License Plate", key="license_plate", placeholder="e.g. KL47N0640")

    # ── Route ────────────────────────────────────────────────────────────
    st.subheader("Route")
    c1, c2 = st.columns(2)
    with c1:
        st.time_input("Pickup Time", key="pickup_time", step=60)
        st.text_area("Pickup Address", key="pickup_address", height=80)
    with c2:
        st.time_input("Dropoff Time", key="dropoff_time", step=60)
        st.text_area("Dropoff Address", key="dropoff_address", height=80)
    c1, c2 = st.columns(2)
    with c1:
        st.number_input("Distance (km)", min_value=0.1, step=0.1,
                        format="%.2f", key="distance_km")
    with c2:
        st.number_input("Duration (min)", min_value=1, step=1, key="duration_min")

    # ── Fare ─────────────────────────────────────────────────────────────
    st.subheader("Fare")
    if st.session_state.vehicle_type == "Uber Go":
        tc = st.number_input("Trip Charge (\u20b9, GST already inside)",
                             min_value=0.0, step=0.50, format="%.2f", key="trip_charge")
        gst = pdf_generator.calc_gst(tc)
        total = pdf_generator.uber_go_total(tc)
        st.caption(f"GST included: \u20b9{gst:.2f}  |  Insurance: \u20b93.00  |  "
                   f"**Total: \u20b9{total:.2f}**")
    else:
        sf = st.number_input("Suggested Fare (\u20b9)",
                             min_value=0.0, step=0.50, format="%.2f", key="suggested_fare")
        total = pdf_generator.auto_total(sf)
        st.caption(f"Booking fee: \u20b91.00  |  Insurance: \u20b93.00  |  "
                   f"**Total: \u20b9{total:.2f}**")

    st.number_input("Uber One Credits Earned (\u20b9, enter 0 if none)",
                    min_value=0.0, step=0.01, format="%.2f", key="uber_one_credits")

    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Payment Method", ["Cash", "UPI Scan and Pay"],
                     key="payment_method")
    with c2:
        st.text_input("Payment Timestamp",
                      placeholder="e.g. 4/10/26 1:54 pm", key="payment_timestamp")

    # ── Driver ───────────────────────────────────────────────────────────
    st.subheader("Driver")
    st.selectbox("Driver Name", INDIAN_DRIVER_NAMES, key="driver_name_select")
    if st.session_state.driver_name_select == "(Enter custom name)":
        st.text_input("Custom Driver Name", key="driver_name_custom")
    st.slider("Driver Rating", min_value=0.0, max_value=5.0,
              step=0.01, format="%.2f", key="driver_rating")

    # ── Navigation ───────────────────────────────────────────────────────
    st.divider()
    fd = _collect_form_data()
    base_fare_ok = (fd.get("trip_charge") or 0) > 0 or (fd.get("suggested_fare") or 0) > 0
    required_ok  = all([
        fd["receipt_date"],
        fd["pickup_address"].strip(),
        fd["dropoff_address"].strip(),
        fd["rider_name"].strip(),
        fd["driver_name"].strip(),
        base_fare_ok,
    ])

    if st.button("Next: Preview Receipt \u2192", type="primary",
                 disabled=not required_ok, use_container_width=True):
        st.session_state.form_data = fd
        st.session_state.step = 2
        st.rerun()

    if not required_ok:
        st.caption("\u26a0\ufe0f  Fill in all required fields (rider name, addresses, fare, "
                   "driver name) to continue.")
```

- [ ] **Step 2: Smoke-test Step 1 renders without error**

```bash
source venv/bin/activate && python3 -c "
import ast, sys
with open('app.py') as f:
    src = f.read()
try:
    ast.parse(src)
    print('app.py syntax OK')
except SyntaxError as e:
    print(f'Syntax error: {e}')
    sys.exit(1)
"
```

Expected: `app.py syntax OK`

---

## Task 6: app.py — Step 2 + main()

**Files:**
- Modify: `app.py` (append `_step2()` and `main()`)

- [ ] **Step 1: Append _step2() and main() to app.py**

Open `app.py` and append at the end:

```python

def _step2():
    st.title("\U0001f697  Uber Receipt Generator")
    st.markdown("### Step 2 of 2 — Preview & Download")

    fd = st.session_state.form_data
    col_left, col_right = st.columns([2, 3])

    with col_left:
        st.markdown("**Receipt Summary**")
        st.markdown(f"**Date:** {fd['receipt_date']}  &nbsp; {fd['receipt_time']}")
        st.markdown(f"**Rider:** {fd['rider_name']}")
        st.markdown(f"**Vehicle:** {fd['vehicle_type']}  |  {fd['license_plate']}")
        st.markdown("---")
        st.markdown(f"**Pickup:** {fd['pickup_time']}")
        st.markdown(f"{fd['pickup_address']}")
        st.markdown(f"**Dropoff:** {fd['dropoff_time']}")
        st.markdown(f"{fd['dropoff_address']}")
        st.markdown(f"*{fd['distance_km']} km  &bull;  {fd['duration_min']} min*")
        st.markdown("---")
        if fd["vehicle_type"] == "Uber Go":
            st.markdown(f"Trip charge: \u20b9{fd['trip_charge']:.2f}")
        else:
            st.markdown(f"Suggested fare: \u20b9{fd['suggested_fare']:.2f}")
            st.markdown("Booking fee: \u20b91.00")
        st.markdown("Insurance: \u20b93.00")
        st.markdown(f"**Total: \u20b9{fd['total']:.2f}**")
        st.markdown(f"Payment: {fd['payment_method']}")
        st.markdown("---")
        st.markdown(f"**Driver:** {fd['driver_name']}  \u2605 {fd['driver_rating']:.2f}")

        st.write("")
        if st.button("\u2190 Back", use_container_width=True):
            st.session_state.step = 1
            st.rerun()

    with col_right:
        st.markdown("#### Generate your receipt PDF")
        st.markdown(
            "Click below to render the receipt. A download button will appear "
            "immediately after.")
        if st.button("\U0001f4c4  Generate Receipt PDF",
                     type="primary", use_container_width=True):
            with st.spinner("Rendering PDF..."):
                pdf_bytes = pdf_generator.generate(fd)
            date_slug = fd["receipt_date"].replace(" ", "_").replace(",", "")
            fname = f"receipt_{date_slug}_{fd['rider_name'].replace(' ', '_')}.pdf"
            st.download_button(
                label=f"\u2b07\ufe0f  Download {fname}",
                data=pdf_bytes,
                file_name=fname,
                mime="application/pdf",
                use_container_width=True,
            )
            st.success(f"Receipt ready: **{fname}**")


def main():
    st.set_page_config(
        page_title="Uber Receipt Generator",
        page_icon="\U0001f697",
        layout="centered",
    )
    _init_state()
    if st.session_state.step == 1:
        _step1()
    else:
        _step2()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify syntax**

```bash
source venv/bin/activate && python3 -c "
import ast
with open('app.py') as f: src = f.read()
ast.parse(src)
print('app.py syntax OK')
"
```

Expected: `app.py syntax OK`

---

## Task 7: End-to-End Smoke Test

- [ ] **Step 1: Run all unit tests**

```bash
source venv/bin/activate && python3 -m pytest tests/ -v
```

Expected: `13 passed` (4 data_loader + 9 pdf_generator)

- [ ] **Step 2: Launch the Streamlit app**

```bash
source venv/bin/activate && streamlit run app.py
```

Expected: Browser opens at `http://localhost:8501`

- [ ] **Step 3: Test the golden path manually**

1. Select template "Hotel 1 to Pallaruthy" from the dropdown → all fields pre-fill
2. Change rider name to something custom → "Next" button becomes active
3. Click "Next: Preview Receipt →" → Step 2 loads with the summary card
4. Click "Generate Receipt PDF" → spinner appears, then a download button
5. Click download → PDF saves locally
6. Open PDF → confirm it shows Uber header, fare table, pickup/dropoff, driver name
7. Click "← Back" → returns to Step 1 with all fields still filled

- [ ] **Step 4: Test Auto vehicle type**

1. Select template "Hotel 2 to Pallarivattom" (Auto receipt)
2. Verify fare section shows "Suggested fare" (not "Trip charge") and no GST note
3. Generate PDF → confirm "Suggested fare" appears and "Trip charge" does not

- [ ] **Step 5: Test scratch mode**

1. Select "— Start from scratch —"
2. "Next" button should be disabled
3. Fill minimum required fields → button enables → generate PDF successfully
