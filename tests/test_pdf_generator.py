import pdf_generator
from pypdf import PdfReader
import io


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
