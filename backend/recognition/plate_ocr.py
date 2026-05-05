"""
License Plate Recognition Engine
================================

Detects the most likely number-plate region in a vehicle image and runs
Tesseract OCR on it.  The pipeline is intentionally simple and pure-Python so
that it works on every machine without needing a GPU or a custom-trained
model.

Pipeline
--------
1.  Read image -> grayscale.
2.  Bilateral filter to reduce noise while keeping edges.
3.  Canny edge detection.
4.  Find contours, keep those whose bounding rectangle has a plate-like
    aspect ratio (roughly 2:1 to 6:1).
5.  Crop the best candidate, threshold it, hand to Tesseract.
6.  Clean the OCR output (uppercase, strip junk characters).

Returns a dict so the caller can decide what to do with each piece of
information (the cropped plate is returned as bytes for storage / debugging).
"""

from __future__ import annotations

import io
import re
from typing import Optional

import cv2
import numpy as np
import pytesseract
from django.conf import settings

# Allow Windows users to override the Tesseract binary location via .env
if getattr(settings, "TESSERACT_CMD", ""):
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

# Characters Tesseract is allowed to output for plates.
_PLATE_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
_TESS_CONFIG = f"--psm 7 --oem 3 -c tessedit_char_whitelist={_PLATE_WHITELIST}"


def _read_image(file_bytes: bytes) -> np.ndarray:
    """Decode raw bytes into an OpenCV BGR image."""
    arr = np.frombuffer(file_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Make sure it is a valid JPG/PNG.")
    return img


def _find_plate_contour(image: np.ndarray) -> Optional[np.ndarray]:
    """Return the cropped plate region or None if nothing plausible is found."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(gray, 30, 200)

    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]

    best = None
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.018 * peri, True)
        if len(approx) == 4:                       # rectangular-ish
            x, y, w, h = cv2.boundingRect(approx)
            ratio = w / float(h) if h else 0
            if 2.0 <= ratio <= 6.0 and w > 60:     # plate-like aspect ratio
                best = (x, y, w, h)
                break

    if best is None:
        return None

    x, y, w, h = best
    return image[y : y + h, x : x + w]


def _clean(text: str) -> str:
    """Strip everything except letters/digits/dashes and uppercase."""
    text = text.upper()
    text = re.sub(r"[^A-Z0-9\-]", "", text)
    return text.strip("-")


def recognize_plate(file_bytes: bytes) -> dict:
    """
    Main entry point.

    Returns
    -------
    {
        "plate_number": "ABC-123" | "",
        "confidence":   "high" | "medium" | "low",
        "raw_text":     <whatever Tesseract spat out>,
        "found_plate":  bool        # was a plate-like region detected
    }
    """
    image = _read_image(file_bytes)
    crop = _find_plate_contour(image)

    target = crop if crop is not None else image       # fall back to full image
    found_plate = crop is not None

    # Pre-process for OCR: gray -> resize-up -> threshold
    gray = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    raw_text = pytesseract.image_to_string(thresh, config=_TESS_CONFIG)
    plate = _clean(raw_text)

    if len(plate) >= 6 and found_plate:
        confidence = "high"
    elif len(plate) >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "plate_number": plate,
        "confidence": confidence,
        "raw_text": raw_text.strip(),
        "found_plate": found_plate,
    }


def encode_crop_as_png(file_bytes: bytes) -> Optional[bytes]:
    """Optionally return the cropped plate as PNG bytes (useful for the UI)."""
    image = _read_image(file_bytes)
    crop = _find_plate_contour(image)
    if crop is None:
        return None
    ok, buf = cv2.imencode(".png", crop)
    return buf.tobytes() if ok else None
