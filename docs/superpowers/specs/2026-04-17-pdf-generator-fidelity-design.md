# PDF Generator Visual Fidelity Upgrade

**Date:** 2026-04-17
**Scope:** Update `pdf_generator.py` so its output matches the original Uber receipt PDFs (e.g. `Hotel 2 to Kalmassery.pdf`) pixel-for-pixel, minus the map (intentionally omitted).

## Reference

All measurements below were extracted from `Hotel 2 to Kalmassery.pdf` using `pdfplumber`.

## Changes

### Page & margins

| Property | Current | Target |
|---|---|---|
| Page size | A4 (595 × 842 pt) | **US Letter (612 × 792 pt)** |
| Margin (all sides) | 10 mm (≈28.3 pt) | **43.5 pt (≈15.3 mm)** |
| Content width | 539 pt | **525 pt** |

### Fonts

We have `UberMove-Bold.ttf` and `UberMove.ttf` (Medium). These substitute for the four variants used in the original (`UberMove-Bold`, `UberMoveText-Regular`, `UberMoveText-Medium`, `UberMoveText-Bold`). Use `UberMove-Bold` for every bold role and `UberMove` for every regular/medium role.

### Font sizes

| Element | Current | Target | Role |
|---|---|---|---|
| "Uber" wordmark | 17 pt Bold | **22 pt Bold** | header |
| Date / time | 8.5 pt | **10.5 pt** | header right |
| "Thanks for riding, X" | 24 pt Bold | **33 pt Bold** | greeting |
| Subtitle "We hope…" | 10 pt | **13.5 pt** | greeting sub |
| "Total" label | 14 pt Bold | **24 pt Bold** | amount row |
| Total amount | 22 pt Bold | **24 pt Bold** | amount row |
| Credits amount (₹24.80) | 11 pt Bold | **13.5 pt Bold** | credits box |
| Credits label | 8 pt | **12 pt** | credits box |
| Fare rows (Trip charge, Insurance) | 10 pt | **12 pt** | fare table |
| "Payments" heading | 13 pt Bold | **18 pt Bold** | section |
| Payment method | 10 pt Bold | **12 pt Bold** | payment row |
| Payment timestamp | 8.5 pt | **10.5 pt** | payment row |
| Disclaimer / link paragraphs | 9 pt | **10.5 pt** | body |
| "Trip details" | 15 pt Bold | **18 pt Bold** | section |
| Vehicle label (Uber Go) | 10 pt Bold | **12 pt Bold** | page 2 |
| Distance / duration | 9 pt | **10.5 pt** | page 2 |
| License plate label | 9 pt | **10.5 pt** | page 2 |
| License plate value | 9 pt Bold | **10.5 pt Bold** | page 2 |
| Pickup / dropoff time | 10 pt Bold | **12 pt Bold** | page 2 |
| Pickup / dropoff address | 9 pt | **10.5 pt** | page 2 |
| "You rode with …" | 11 pt Bold | **12 pt Bold** | page 2 |
| "My trips" link | 9 pt | **12 pt** | page 2 |

### Structural / element changes

1. **Uber One logo** — Debug and fix why `uber_one_logo.png` is not rendering (currently falling back to amber "⊕ Uber One" text). Target height ≈ 16 pt (same order as the original, which is a small rounded pill badge).

2. **Page 2 vehicle icon** — Reduce from 32 pt tall to ~18 pt tall (matches original proportions).

3. **Page 2 route pins** — Resize:
   - Pickup circle: radius 4 → **5.5 pt** (11 pt diameter)
   - Dropoff square: side 8 → **10 pt**
   - Connecting line stays solid 1.5 pt wide (already correct).

4. **Page 2 address column** — Keep **full width** (map area unused). Wrap width = full `CW`.

5. **Single payment method only** — No multi-payment support. Cash is the primary case.

### Non-goals

- Map rendering on page 2 (explicitly omitted — user doesn't need it).
- Multi-payment rows / failed-payment state.
- Sourcing UberMoveText font variants (use UberMove-Bold / UberMove throughout).
- Any changes to `app.py`, `data_loader.py`, or the receipt form.

## Acceptance

- Generated PDF's page 1 header, greeting, total, credits box, fare table, payments section, and disclaimer paragraphs are visually within a few percent of the original.
- Generated PDF's page 2 vehicle row, route pins, addresses, driver row, and trip-history link are visually within a few percent of the original.
- Uber One subscription badge renders as the PNG logo, not the amber fallback text.
- Existing unit tests in `tests/` still pass.
