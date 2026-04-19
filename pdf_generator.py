"""Uber-style receipt PDF generator — 2-page US Letter matching real Uber receipts."""
import io
import math
import os
import urllib.request

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
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
C_ABLBL  = colors.HexColor("#000000")
C_BLUE   = colors.HexColor("#276EF1")

PAGE_W, PAGE_H = letter          # 612 × 792 pt — matches original Uber receipt
M  = 43.5                         # ~15.3 mm — matches original margin exactly
CW = PAGE_W - 2 * M               # 525 pt content width

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
        if not dims or dims[1] == 0:
            return 0
        width = height * dims[0] / dims[1]
        # Don't pass preserveAspectRatio=True together with explicit width:
        # ReportLab treats that combo as "fit inside" and may not draw at all.
        # We've already computed the exact aspect-preserving width, so drop it.
        c.drawImage(path, x, y_top - height, width=width, height=height,
                    mask="auto")
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
    c   = pdf_canvas.Canvas(buf, pagesize=letter)
    W, H = PAGE_W, PAGE_H

    vtype   = form_data.get("vehicle_type", "Uber Go")
    credits = float(form_data.get("uber_one_credits") or 0)
    total   = float(form_data.get("total") or 0)
    is_u1   = bool(form_data.get("is_uber_one", False)) or credits > 0

    # ═══════════════════════════════════════════════════════
    # PAGE 1
    # ═══════════════════════════════════════════════════════
    y = H - M

    # ── Header: Uber wordmark (text) + date/time ────────────
    c.setFont(B, 30)
    c.setFillColor(C_DARK)
    c.drawString(M, y - 28, "Uber")

    c.setFont(F, 10.5)
    c.setFillColor(C_GRAY)
    c.drawRightString(W - M, y - 12, form_data.get("receipt_date", ""))
    c.drawRightString(W - M, y - 26, form_data.get("receipt_time", ""))
    y -= 52

    # ── Uber One subscription badge (⊕ Uber One image) ──────
    if is_u1:
        LOGO_H = 24          # matches original badge 24pt height
        w = _draw_image(c, os.path.join(ICONS_DIR, "uber_one_logo.png"),
                        M, y, LOGO_H)
        if w == 0:           # fallback if image missing
            c.setFont(B, 14)
            c.setFillColor(C_AMBER)
            c.drawString(M, y - 14, "\u2295  Uber One")
        y -= LOGO_H + 22

    # ── Greeting ─────────────────────────────────────────────
    name = form_data.get("rider_name", "")
    c.setFont(B, 33)
    c.setFillColor(C_DARK)
    c.drawString(M, y - 33, f"Thanks for riding, {name}")
    y -= 42

    c.setFont(F, 13.5)
    c.setFillColor(C_GRAY)
    c.drawString(M, y - 14, f"We hope you enjoyed your ride {_time_greeting(form_data.get('receipt_time',''))}.")
    y -= 38

    # ── Total ────────────────────────────────────────────────
    c.setFont(B, 24)
    c.setFillColor(C_DARK)
    c.drawString(M, y - 24, "Total")
    c.setFont(B, 24)
    c.drawRightString(W - M, y - 24, f"\u20b9{total:.2f}")
    y -= 40

    _hr(c, y)
    y -= 14

    # ── Uber One credits earned box ──────────────────────────
    if credits > 0:
        BOX_H  = 56
        ICON_H = 22
        PAD_L  = 14
        PAD_T  = 12

        c.setFillColor(C_ABGND)
        c.roundRect(M, y - BOX_H, CW, BOX_H, 8, stroke=0, fill=1)

        # Icon top-aligned with amount text
        icon_w   = _draw_image(c, os.path.join(ICONS_DIR, "uber_one_icon.png"),
                               M + PAD_L, y - PAD_T, ICON_H)

        text_x = M + PAD_L + (icon_w or 0) + 10
        c.setFont(B, 13.5)
        c.setFillColor(C_AMBER)
        c.drawString(text_x, y - PAD_T - 12, f"\u20b9{credits:.2f}")
        c.setFont(F, 12)
        c.setFillColor(C_ABLBL)
        c.drawString(text_x, y - PAD_T - 30, "Uber One credits earned")

        y -= BOX_H + 12

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
        c.setFont(F, 12)
        c.setFillColor(C_DARK)
        c.drawString(M, y - 14, label)
        c.drawRightString(W - M, y - 14, amount)
        y -= 28

    y -= 12

    _hr(c, y)
    y -= 18

    # ── Payments ─────────────────────────────────────────────
    c.setFont(B, 18)
    c.setFillColor(C_DARK)
    c.drawString(M, y - 18, "Payments")
    y -= 32

    pm        = form_data.get("payment_method", "Cash")
    icon_file = "cash.png" if pm == "Cash" else "upi.png"
    PAY_H     = 26
    icon_w    = _draw_image(c, os.path.join(ICONS_DIR, icon_file), M, y, PAY_H)
    tx        = M + (icon_w + 10 if icon_w else 0)

    # Method name + amount on top row
    c.setFont(B, 12)
    c.setFillColor(C_DARK)
    c.drawString(tx, y - 12, pm)
    c.drawRightString(W - M, y - 12, f"\u20b9{total:.2f}")

    # Timestamp directly below method, tight spacing
    if form_data.get("payment_timestamp"):
        c.setFont(F, 10.5)
        c.setFillColor(C_GRAY)
        c.drawString(tx, y - 26, str(form_data["payment_timestamp"]))

    y -= PAY_H + 16
    _hr(c, y)
    y -= 20

    # ── Disclaimer paragraphs ─────────────────────────────────
    LH = 14

    if vtype == "Uber Go":
        tc  = float(form_data.get("trip_charge") or 0)
        gst = calc_gst(tc)
        paras = [
            "Visit the trip page for more information, including invoices (where available).",
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

    c.setFont(F, 10.5)
    default_fill = C_DARK if vtype == "Uber Go" else C_GRAY
    for p_idx, para in enumerate(paras):
        for i, ln in enumerate(_wrap(para, F, 10.5, CW)):
            if i == 0 and ln.startswith("Visit the trip page"):
                link_text = "Visit the trip page"
                tail_text = ln[len(link_text):]
                link_w    = pdfmetrics.stringWidth(link_text, F, 10.5)
                c.setFillColor(C_BLUE)
                c.drawString(M, y - 12, link_text)
                c.setStrokeColor(C_BLUE)
                c.setLineWidth(0.5)
                c.line(M, y - 13.5, M + link_w, y - 13.5)
                c.linkURL("https://riders.uber.com/trips/",
                          (M, y - 14, M + link_w, y - 2), relative=0)
                c.setFillColor(default_fill)
                c.drawString(M + link_w, y - 12, tail_text)
            else:
                c.setFillColor(default_fill)
                c.drawString(M, y - 12, ln)
            y -= LH
        y -= 8
        # Light separator between paragraphs
        if p_idx < len(paras) - 1:
            _hr(c, y)
            y -= 14

    # ═══════════════════════════════════════════════════════
    # PAGE 2
    # ═══════════════════════════════════════════════════════
    c.showPage()
    y = H - M

    # ── "Trip details" section heading (now on page 2) ──────
    c.setFont(B, 18)
    c.setFillColor(C_DARK)
    c.drawString(M, y - 18, "Trip details")
    y -= 34

    # ── Vehicle row ──────────────────────────────────────────
    veh_file = "uber_go.png" if vtype == "Uber Go" else "auto.png"
    VEH_H    = 18
    icon_w   = _draw_image(c, os.path.join(ICONS_DIR, veh_file), M, y, VEH_H)
    tx       = M + (icon_w + 10 if icon_w else 0)

    c.setFont(B, 12)
    c.setFillColor(C_DARK)
    c.drawString(tx, y - 12, vtype)
    c.setFont(F, 10.5)
    c.setFillColor(C_GRAY)
    c.drawString(tx, y - 27, f"{form_data.get('distance_km','')} kilometres, {form_data.get('duration_min','')} minutes")

    c.setFont(F, 10.5)
    c.setFillColor(C_GRAY)
    c.drawRightString(W - M, y - 12, "License Plate:")
    c.setFont(B, 10.5)
    c.setFillColor(C_DARK)
    c.drawRightString(W - M, y - 27, str(form_data.get("license_plate", "")))

    y -= VEH_H + 22
    _hr(c, y)
    y -= 28

    # ── Route ────────────────────────────────────────────────
    PIN_X  = M + 12       # pin centered ~17pt from left edge
    TEXT_X = M + 28       # text column starts 28pt from left (wider gap)
    TEXT_W = CW - 28      # full-width addresses (no map to the right)

    pu_y = y
    c.setFillColor(C_DARK)
    c.circle(PIN_X, pu_y - 9, 5.5, stroke=0, fill=1)      # 11pt diameter
    c.setFont(B, 12)
    c.setFillColor(C_DARK)
    c.drawString(TEXT_X, pu_y - 12, str(form_data.get("pickup_time", "")))
    c.setFont(F, 10.5)
    c.setFillColor(C_GRAY)
    pu_lines = _wrap(str(form_data.get("pickup_address", "")), F, 10.5, TEXT_W)[:4]
    for i, ln in enumerate(pu_lines):
        c.drawString(TEXT_X, pu_y - 28 - i * 14, ln)
    pu_h = 28 + len(pu_lines) * 14

    do_y = pu_y - pu_h - 18
    c.setStrokeColor(C_LINE)
    c.setLineWidth(1.5)
    c.line(PIN_X, pu_y - 16, PIN_X, do_y + 7)

    sq = 10                                                # 10pt square
    c.setFillColor(C_DARK)
    c.rect(PIN_X - sq / 2, do_y - sq / 2, sq, sq, stroke=0, fill=1)
    c.setFont(B, 12)
    c.setFillColor(C_DARK)
    c.drawString(TEXT_X, do_y - 5, str(form_data.get("dropoff_time", "")))
    c.setFont(F, 10.5)
    c.setFillColor(C_GRAY)
    do_lines = _wrap(str(form_data.get("dropoff_address", "")), F, 10.5, TEXT_W)[:4]
    for i, ln in enumerate(do_lines):
        c.drawString(TEXT_X, do_y - 20 - i * 14, ln)
    do_h = 20 + len(do_lines) * 14

    y = do_y - do_h - 24
    _hr(c, y)
    y -= 26

    # ── Driver (plain text + drawn star) ─────────────────────
    driver_name   = str(form_data.get("driver_name", ""))
    driver_rating = float(form_data.get("driver_rating") or 0)
    rating_str    = f"{driver_rating:.2f}"

    c.setFont(B, 12)
    c.setFillColor(C_DARK)
    c.drawString(M, y - 14, f"You rode with {driver_name}.")

    # Rating text + star drawn as polygon
    STAR_R  = 6
    rating_w = pdfmetrics.stringWidth(rating_str, B, 12)
    # Right-align: star is rightmost, rating text to its left
    star_cx = W - M - STAR_R - 1
    rat_x   = star_cx - STAR_R - 6 - rating_w
    c.drawString(rat_x, y - 14, rating_str)
    _draw_star(c, star_cx, y - 10, r=STAR_R, fill_color=C_DARK)

    y -= 36

    # ── "Want to review your trip history?" ──────────────────
    c.setFont(F, 12)
    c.setFillColor(C_GRAY)
    c.drawString(M, y - 14, "Want to review your trip history?")
    c.setFillColor(C_BLUE)
    c.drawRightString(W - M, y - 14, "My trips")

    c.save()
    return buf.getvalue()
