"""Uber-style receipt PDF generator — 2-page A4 matching real Uber receipts."""
import io
import math
import os
import urllib.request

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR     = os.path.join(BASE_DIR, "assets", "fonts")
ICONS_DIR     = os.path.join(BASE_DIR, "assets", "icons")
UBER_FONT_DIR = os.path.join(BASE_DIR, "Uber Font")

C_DARK   = colors.HexColor("#1A1A1A")
C_GRAY   = colors.HexColor("#6B6B6B")
C_LINE   = colors.HexColor("#E0E0E0")
C_AMBER  = colors.HexColor("#976722")
C_ABGND  = colors.HexColor("#F3F3F3")   # lighter warm beige — matches real receipt
C_ABLBL  = colors.HexColor("#8B6914")
C_BLUE   = colors.HexColor("#276EF1")

PAGE_W, PAGE_H = A4
M  = 10 * mm        # ~10 mm — matches real Uber receipt margins
CW = PAGE_W - 2 * M

GST_RATE    = 0.0707
INSURANCE   = 3.00
BOOKING_FEE = 1.00

_fonts_loaded: tuple | None = None


# ─────────────────────────────────────────────────────────────
# OTF → TTF conversion (CFF outlines → TrueType outlines)
# ─────────────────────────────────────────────────────────────

def _convert_otf_to_ttf(src: str, dst: str) -> None:
    """Convert a CFF-based OTF file to a TTF file ReportLab can load."""
    from fontTools.ttLib import TTFont as FTFont, newTable
    from fontTools.ttLib.tables._g_l_y_f import Glyph
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    font = FTFont(src)
    glyphset   = font.getGlyphSet()
    order      = font.getGlyphOrder()
    glyf_glyphs = {}
    for name in order:
        pen = TTGlyphPen(None)
        try:
            glyphset[name].draw(pen)
            glyf_glyphs[name] = pen.glyph()
        except Exception:
            glyf_glyphs[name] = Glyph()

    glyf           = newTable("glyf")
    glyf.glyphs    = glyf_glyphs
    glyf.glyphOrder = order
    font["glyf"]   = glyf
    font["loca"]   = newTable("loca")
    del font["CFF "]

    # maxp version 1.0 required for TrueType
    font["maxp"].tableVersion = 0x00010000
    for field in ("maxZones", "maxTwilightPoints", "maxStorage",
                  "maxFunctionDefs", "maxInstructionDefs", "maxStackElements",
                  "maxSizeOfInstructions", "maxComponentElements", "maxComponentDepth"):
        if not hasattr(font["maxp"], field):
            setattr(font["maxp"], field, 0)

    font.sfntVersion         = "\x00\x01\x00\x00"
    font["head"].magicNumber = 0x5F0F3CF5
    font.save(dst)


# ─────────────────────────────────────────────────────────────
# Font loading — UberMove preferred, NotoSans fallback
# ─────────────────────────────────────────────────────────────

def _load_fonts() -> tuple:
    global _fonts_loaded
    if _fonts_loaded:
        return _fonts_loaded

    # 1. Try UberMove — convert OTF→TTF once if needed, then register
    os.makedirs(FONTS_DIR, exist_ok=True)
    uber_med_ttf  = os.path.join(FONTS_DIR, "UberMove.ttf")
    uber_bold_ttf = os.path.join(FONTS_DIR, "UberMove-Bold.ttf")
    uber_med_otf  = os.path.join(UBER_FONT_DIR, "UberMoveMedium.otf")
    uber_bold_otf = os.path.join(UBER_FONT_DIR, "UberMoveBold.otf")

    if os.path.exists(uber_med_otf) and os.path.exists(uber_bold_otf):
        # Convert CFF-based OTF → TTF if not done yet
        if not os.path.exists(uber_med_ttf) or not os.path.exists(uber_bold_ttf):
            try:
                _convert_otf_to_ttf(uber_med_otf,  uber_med_ttf)
                _convert_otf_to_ttf(uber_bold_otf, uber_bold_ttf)
            except Exception:
                pass

        if os.path.exists(uber_med_ttf) and os.path.exists(uber_bold_ttf):
            try:
                reg = pdfmetrics.getRegisteredFontNames()
                if "UberMove" not in reg:
                    pdfmetrics.registerFont(TTFont("UberMove", uber_med_ttf))
                if "UberMove-Bold" not in reg:
                    pdfmetrics.registerFont(TTFont("UberMove-Bold", uber_bold_ttf))
                _fonts_loaded = ("UberMove", "UberMove-Bold")
                return _fonts_loaded
            except Exception:
                pass

    # 2. Fall back to NotoSans (downloaded once)
    os.makedirs(FONTS_DIR, exist_ok=True)
    reg_path  = os.path.join(FONTS_DIR, "NotoSans-Regular.ttf")
    bold_path = os.path.join(FONTS_DIR, "NotoSans-Bold.ttf")
    urls = {
        reg_path:  "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
        bold_path: "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
    }
    for path, url in urls.items():
        if not os.path.exists(path):
            try:
                urllib.request.urlretrieve(url, path)
            except Exception:
                _fonts_loaded = ("Helvetica", "Helvetica-Bold")
                return _fonts_loaded
    try:
        reg = pdfmetrics.getRegisteredFontNames()
        if "NotoSans" not in reg:
            pdfmetrics.registerFont(TTFont("NotoSans", reg_path))
        if "NotoSans-Bold" not in reg:
            pdfmetrics.registerFont(TTFont("NotoSans-Bold", bold_path))
        _fonts_loaded = ("NotoSans", "NotoSans-Bold")
    except Exception:
        _fonts_loaded = ("Helvetica", "Helvetica-Bold")
    return _fonts_loaded


# ─────────────────────────────────────────────────────────────
# Icon extraction from original PDFs
# ─────────────────────────────────────────────────────────────

def _extract_icons() -> None:
    try:
        from pypdf import PdfReader
        from PIL import Image as PILImage
    except ImportError:
        return

    os.makedirs(ICONS_DIR, exist_ok=True)

    def _get_obj(pdf_name, page_idx, obj_key):
        pdf_path = os.path.join(BASE_DIR, pdf_name)
        if not os.path.exists(pdf_path):
            return None
        try:
            reader = PdfReader(pdf_path)
            if page_idx >= len(reader.pages):
                return None
            xobjs = (reader.pages[page_idx].get("/Resources") or {}).get("/XObject") or {}
            return xobjs.get(obj_key)
        except Exception:
            return None

    def _save_rgb(obj, dest):
        if obj is None or os.path.exists(dest):
            return False
        try:
            w, h = int(obj.get("/Width", 0)), int(obj.get("/Height", 0))
            img  = PILImage.frombytes("RGB", (w, h), obj.get_data())
            smask = obj.get("/SMask")
            if smask:
                sw, sh = int(smask.get("/Width", 0)), int(smask.get("/Height", 0))
                alpha  = PILImage.frombytes("L", (sw, sh), smask.get_data())
                r, g, b = img.split()
                img = PILImage.merge("RGBA", (r, g, b, alpha))
            img.save(dest, "PNG")
            return True
        except Exception:
            return False

    src = "Hotel 2 to Kalmassery.pdf"
    _save_rgb(_get_obj(src, 0, "/X5"),  os.path.join(ICONS_DIR, "uber_one_logo.png"))  # 280×96
    _save_rgb(_get_obj(src, 0, "/X15"), os.path.join(ICONS_DIR, "uber_one_icon.png"))  # 60×60
    _save_rgb(_get_obj(src, 0, "/X16"), os.path.join(ICONS_DIR, "cash.png"))           # 72×72
    _save_rgb(_get_obj(src, 0, "/X18"), os.path.join(ICONS_DIR, "upi.png"))            # 60×60
    _save_rgb(_get_obj(src, 1, "/X25"), os.path.join(ICONS_DIR, "uber_go.png"))        # 280×280
    _save_rgb(_get_obj("Kalamassery to Hotel 2.pdf", 1, "/X24"),
              os.path.join(ICONS_DIR, "auto.png"))                                     # 360×360


# ─────────────────────────────────────────────────────────────
# Public fare helpers
# ─────────────────────────────────────────────────────────────

def calc_gst(trip_charge: float) -> float:
    return round(trip_charge * GST_RATE, 2)

def uber_go_total(trip_charge: float) -> float:
    return round(trip_charge + INSURANCE, 2)

def auto_total(suggested_fare: float) -> float:
    return round(suggested_fare + BOOKING_FEE + INSURANCE, 2)


# ─────────────────────────────────────────────────────────────
# Private drawing helpers
# ─────────────────────────────────────────────────────────────

def _img_dims(path: str):
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as img:
            return img.size          # (w, h)
    except Exception:
        return None


def _draw_image(c, path: str, x: float, y_top: float, height: float) -> float:
    """Draw image with top-left at (x, y_top) at given height; returns width drawn."""
    if not os.path.exists(path):
        return 0
    try:
        dims = _img_dims(path)
        width = height * dims[0] / dims[1] if dims else height
        c.drawImage(path, x, y_top - height, width, height,
                    mask="auto", preserveAspectRatio=True)
        return width
    except Exception:
        return 0


def _wrap(text: str, font: str, size: float, max_w: float) -> list:
    words = text.split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        if pdfmetrics.stringWidth(test, font, size) <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines or [""]


def _hr(c, y: float, lw: float = 0.5) -> None:
    c.setStrokeColor(C_LINE)
    c.setLineWidth(lw)
    c.line(M, y, PAGE_W - M, y)


def _draw_star(c, cx: float, cy: float, r: float = 5.0, fill_color=None) -> None:
    """Solid 5-pointed star centred at (cx, cy)."""
    if fill_color:
        c.setFillColor(fill_color)
    inner_r = r * 0.382
    path = c.beginPath()
    for i in range(5):
        oa = math.pi / 2 + 2 * math.pi * i / 5
        ia = oa + math.pi / 5
        if i == 0:
            path.moveTo(cx + r * math.cos(oa), cy + r * math.sin(oa))
        else:
            path.lineTo(cx + r * math.cos(oa), cy + r * math.sin(oa))
        path.lineTo(cx + inner_r * math.cos(ia), cy + inner_r * math.sin(ia))
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def _time_greeting(receipt_time: str) -> str:
    try:
        raw  = receipt_time.strip().lower()
        is_pm = "pm" in raw
        h    = int(raw.replace("am", "").replace("pm", "").strip().split(":")[0])
        if is_pm and h != 12:
            h += 12
        elif not is_pm and h == 12:
            h = 0
        if 5 <= h < 12:  return "this morning"
        if 12 <= h < 17: return "this afternoon"
        if 17 <= h < 21: return "this evening"
        return "tonight"
    except Exception:
        return "this evening"


# ─────────────────────────────────────────────────────────────
# Main generator
# ─────────────────────────────────────────────────────────────

def generate(form_data: dict) -> bytes:
    _extract_icons()
    F, B = _load_fonts()

    buf = io.BytesIO()
    c   = pdf_canvas.Canvas(buf, pagesize=A4)
    W, H = PAGE_W, PAGE_H

    vtype   = form_data.get("vehicle_type", "Uber Go")
    credits = float(form_data.get("uber_one_credits") or 0)
    total   = float(form_data.get("total") or 0)
    is_u1   = bool(form_data.get("is_uber_one", False)) or credits > 0

    # ═══════════════════════════════════════════════════════
    # PAGE 1
    # ═══════════════════════════════════════════════════════
    y = H - M

    # ── Header: Uber wordmark + date/time ───────────────────
    c.setFont(B, 17)
    c.setFillColor(C_DARK)
    c.drawString(M, y - 18, "Uber")

    c.setFont(F, 8.5)
    c.setFillColor(C_GRAY)
    c.drawRightString(W - M, y - 11, form_data.get("receipt_date", ""))
    c.drawRightString(W - M, y - 22, form_data.get("receipt_time", ""))
    y -= 32

    # ── Uber One subscription badge (actual logo image) ──────
    if is_u1:
        logo_path = os.path.join(ICONS_DIR, "uber_one_logo.png")
        LOGO_H = 12          # 12 pt tall — matches real receipt badge size
        w = _draw_image(c, logo_path, M, y, LOGO_H)
        if w == 0:           # fallback if image missing
            c.setFont(B, 9)
            c.setFillColor(C_AMBER)
            c.drawString(M, y - 10, "\u2295  Uber One")
        y -= LOGO_H + 18

    # ── Greeting ─────────────────────────────────────────────
    name = form_data.get("rider_name", "")
    c.setFont(B, 24)
    c.setFillColor(C_DARK)
    c.drawString(M, y - 24, f"Thanks for riding, {name}")
    y -= 32

    c.setFont(F, 10)
    c.setFillColor(C_GRAY)
    c.drawString(M, y - 13, f"We hope you enjoyed your ride {_time_greeting(form_data.get('receipt_time',''))}.")
    y -= 30

    # ── Total ────────────────────────────────────────────────
    c.setFont(B, 14)
    c.setFillColor(C_DARK)
    c.drawString(M, y - 16, "Total")
    c.setFont(B, 22)
    c.drawRightString(W - M, y - 18, f"\u20b9{total:.2f}")
    y -= 30

    _hr(c, y)
    y -= 14

    # ── Uber One credits earned box ──────────────────────────
    if credits > 0:
        BOX_H  = 42
        ICON_H = 18
        PAD_L  = 10
        PAD_T  = 9

        c.setFillColor(C_ABGND)
        c.roundRect(M, y - BOX_H, CW, BOX_H, 6, stroke=0, fill=1)

        # Icon top-aligned with amount text
        icon_w   = _draw_image(c, os.path.join(ICONS_DIR, "uber_one_icon.png"),
                               M + PAD_L, y - PAD_T, ICON_H)

        text_x = M + PAD_L + (icon_w or 0) + 8
        c.setFont(B, 11)
        c.setFillColor(C_AMBER)
        c.drawString(text_x, y - PAD_T - 10, f"\u20b9{credits:.2f}")
        c.setFont(F, 8)
        c.setFillColor(C_ABLBL)
        c.drawString(text_x, y - PAD_T - 23, "Uber One credits earned")

        y -= BOX_H + 8

    # ── Fare rows ────────────────────────────────────────────
    if vtype == "Uber Go":
        tc = float(form_data.get("trip_charge") or 0)
        rows = [("Trip charge", f"\u20b9{tc:.2f}"),
                ("Insurance",   f"\u20b9{INSURANCE:.2f}")]
    else:
        sf = float(form_data.get("suggested_fare") or 0)
        rows = [("Suggested fare", f"\u20b9{sf:.2f}"),
                ("Booking fee",    f"\u20b9{BOOKING_FEE:.2f}"),
                ("Insurance",      f"\u20b9{INSURANCE:.2f}")]

    for label, amount in rows:
        c.setFont(F, 10)
        c.setFillColor(C_DARK)
        c.drawString(M, y - 14, label)
        c.drawRightString(W - M, y - 14, amount)
        y -= 22

    y -= 10

    _hr(c, y)
    y -= 18

    # ── Payments ─────────────────────────────────────────────
    c.setFont(B, 13)
    c.setFillColor(C_DARK)
    c.drawString(M, y - 14, "Payments")
    y -= 24

    pm        = form_data.get("payment_method", "Cash")
    icon_file = "cash.png" if pm == "Cash" else "upi.png"
    PAY_H     = 20
    icon_w    = _draw_image(c, os.path.join(ICONS_DIR, icon_file), M, y, PAY_H)
    tx        = M + (icon_w + 8 if icon_w else 0)

    # Method name + amount on top row
    c.setFont(B, 10)
    c.setFillColor(C_DARK)
    c.drawString(tx, y - 10, pm)
    c.drawRightString(W - M, y - 10, f"\u20b9{total:.2f}")

    # Timestamp directly below method, tight spacing
    if form_data.get("payment_timestamp"):
        c.setFont(F, 8.5)
        c.setFillColor(C_GRAY)
        c.drawString(tx, y - 22, str(form_data["payment_timestamp"]))

    y -= PAY_H + 14
    _hr(c, y)
    y -= 16

    # ── Disclaimer paragraphs ─────────────────────────────────
    LH = 12

    if vtype == "Uber Go":
        # "Visit the trip page..." link line
        link_text = "Visit the trip page"
        tail_text = " for more information, including invoices (where available)."
        c.setFont(F, 9)
        c.setFillColor(C_BLUE)
        c.drawString(M, y - 11, link_text)
        link_w = pdfmetrics.stringWidth(link_text, F, 9)
        # underline link
        c.setStrokeColor(C_BLUE)
        c.setLineWidth(0.4)
        c.line(M, y - 12.5, M + link_w, y - 12.5)
        c.setFillColor(C_DARK)
        c.drawString(M + link_w, y - 11, tail_text)
        y -= LH + 10

        tc  = float(form_data.get("trip_charge") or 0)
        gst = calc_gst(tc)
        paras = [
            f"The total of \u20b9{total:.2f} has a GST of \u20b9{gst:.2f} included.",
            "Fares are inclusive of GST. Please download the tax invoice from the trip detail page for a full tax breakdown.",
        ]
    else:
        paras = [
            ("This receipt reflects the suggested fare (excluding GST) and is not a tax invoice "
             "but can be used for official reimbursement purposes. No GST is being recovered by "
             "Uber from the riders on this trip."),
            ("This trip receipt is not the legal receipt of your trip for the purpose of local "
             "laws. Upon completion of the trip, you have the right to demand a receipt from your "
             "driver, which shall be the legal receipt of your trip. The trip payment (including "
             "tolls, surcharges and other fees that may be permitted by local laws and regulations) "
             "is provided by your driver, who is solely responsible for its calculation in "
             "accordance with local laws and regulations."),
        ]

    c.setFont(F, 9)
    c.setFillColor(C_DARK if vtype == "Uber Go" else C_GRAY)
    for para in paras:
        for ln in _wrap(para, F, 9, CW):
            c.drawString(M, y - 11, ln)
            y -= LH
        y -= 6

    # ── "Trip details" section heading ───────────────────────
    y -= 6
    _hr(c, y)
    y -= 20
    c.setFont(B, 15)
    c.setFillColor(C_DARK)
    c.drawString(M, y - 15, "Trip details")

    # ═══════════════════════════════════════════════════════
    # PAGE 2
    # ═══════════════════════════════════════════════════════
    c.showPage()
    y = H - M

    # ── Vehicle row ──────────────────────────────────────────
    veh_file = "uber_go.png" if vtype == "Uber Go" else "auto.png"
    VEH_H    = 32
    icon_w   = _draw_image(c, os.path.join(ICONS_DIR, veh_file), M, y, VEH_H)
    tx       = M + (icon_w + 10 if icon_w else 0)

    c.setFont(B, 10)
    c.setFillColor(C_DARK)
    c.drawString(tx, y - 13, vtype)
    c.setFont(F, 9)
    c.setFillColor(C_GRAY)
    c.drawString(tx, y - 25, f"{form_data.get('distance_km','')} kilometres, {form_data.get('duration_min','')} minutes")

    c.setFont(F, 9)
    c.setFillColor(C_GRAY)
    c.drawRightString(W - M, y - 13, "License Plate:")
    c.setFont(B, 9)
    c.setFillColor(C_DARK)
    c.drawRightString(W - M, y - 25, str(form_data.get("license_plate", "")))

    y -= VEH_H + 14
    _hr(c, y)
    y -= 24

    # ── Route ────────────────────────────────────────────────
    PIN_X  = M + 8
    TEXT_X = M + 22
    TEXT_W = CW - 22

    pu_y = y
    c.setFillColor(C_DARK)
    c.circle(PIN_X, pu_y - 7, 4, stroke=0, fill=1)
    c.setFont(B, 10)
    c.setFillColor(C_DARK)
    c.drawString(TEXT_X, pu_y - 10, str(form_data.get("pickup_time", "")))
    c.setFont(F, 9)
    c.setFillColor(C_GRAY)
    pu_lines = _wrap(str(form_data.get("pickup_address", "")), F, 9, TEXT_W)[:3]
    for i, ln in enumerate(pu_lines):
        c.drawString(TEXT_X, pu_y - 22 - i * 12, ln)
    pu_h = 22 + len(pu_lines) * 12

    do_y = pu_y - pu_h - 14
    c.setStrokeColor(C_LINE)
    c.setLineWidth(1.2)
    c.line(PIN_X, pu_y - 12, PIN_X, do_y + 8)

    sq = 8
    c.setFillColor(C_DARK)
    c.rect(PIN_X - sq / 2, do_y - sq / 2, sq, sq, stroke=0, fill=1)
    c.setFont(B, 10)
    c.setFillColor(C_DARK)
    c.drawString(TEXT_X, do_y - 5, str(form_data.get("dropoff_time", "")))
    c.setFont(F, 9)
    c.setFillColor(C_GRAY)
    do_lines = _wrap(str(form_data.get("dropoff_address", "")), F, 9, TEXT_W)[:3]
    for i, ln in enumerate(do_lines):
        c.drawString(TEXT_X, do_y - 17 - i * 12, ln)
    do_h = 17 + len(do_lines) * 12

    y = do_y - do_h - 20
    _hr(c, y)
    y -= 20

    # ── Driver (plain text + drawn star) ─────────────────────
    driver_name   = str(form_data.get("driver_name", ""))
    driver_rating = float(form_data.get("driver_rating") or 0)
    rating_str    = f"{driver_rating:.2f}"

    c.setFont(B, 11)
    c.setFillColor(C_DARK)
    c.drawString(M, y - 14, f"You rode with {driver_name}.")

    # Rating text + star drawn as polygon
    STAR_R  = 5
    rating_w = pdfmetrics.stringWidth(rating_str, B, 11)
    # Right-align: star is rightmost, rating text to its left
    star_cx = W - M - STAR_R - 1
    rat_x   = star_cx - STAR_R - 5 - rating_w
    c.drawString(rat_x, y - 14, rating_str)
    _draw_star(c, star_cx, y - 9, r=STAR_R, fill_color=C_DARK)

    y -= 28

    # ── "Want to review your trip history?" ──────────────────
    c.setFont(F, 9)
    c.setFillColor(C_GRAY)
    c.drawString(M, y - 13, "Want to review your trip history?")
    c.setFillColor(C_BLUE)
    c.drawRightString(W - M, y - 13, "My trips")

    c.save()
    return buf.getvalue()
