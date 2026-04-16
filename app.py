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
        "is_uber_one": False,
        "uber_one_credits": 0.0,
        "payment_method": "Cash",
        "payment_timestamp": "",
        "driver_name_select": INDIAN_DRIVER_NAMES[0],
        "driver_name_custom": "",
        "driver_rating": 4.90,
        "pdf_bytes": None,
        "pdf_fname": "",
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
    credits = fare.get("uber_one_credits_earned") or 0.0
    st.session_state.uber_one_credits = credits
    st.session_state.is_uber_one = credits > 0

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
        trip_charge    = ss.trip_charge
        suggested_fare = None
        total = pdf_generator.uber_go_total(trip_charge)
    else:
        trip_charge    = None
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
        "is_uber_one":       ss.is_uber_one,
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

    st.checkbox("\u2295  Uber One subscriber (shows subscription badge on receipt)",
                key="is_uber_one")
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
            st.session_state.pdf_bytes = None
            st.session_state.pdf_fname = ""
            st.rerun()

    with col_right:
        st.markdown("#### Generate your receipt PDF")
        st.markdown(
            "Click below to render the receipt. The download button will stay "
            "available until you go back.")
        if st.button("\U0001f4c4  Generate Receipt PDF",
                     type="primary", use_container_width=True):
            with st.spinner("Rendering PDF..."):
                try:
                    pdf_bytes = pdf_generator.generate(fd)
                except Exception as e:
                    st.error(f"Failed to generate receipt: {e}")
                    pdf_bytes = None
            if pdf_bytes:
                date_slug = fd["receipt_date"].replace(" ", "_").replace(",", "")
                fname = f"receipt_{date_slug}_{fd['rider_name'].replace(' ', '_')}.pdf"
                st.session_state.pdf_bytes = pdf_bytes
                st.session_state.pdf_fname = fname

        if st.session_state.get("pdf_bytes"):
            fname = st.session_state.pdf_fname
            st.download_button(
                label=f"\u2b07\ufe0f  Download {fname}",
                data=st.session_state.pdf_bytes,
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
