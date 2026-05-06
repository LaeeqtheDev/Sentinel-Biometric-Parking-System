"""
License Plate Recognition Engine — v2 (multi-pass)
==================================================

The v1 pipeline was too simple: one preprocessing pass, one PSM, no quality
gating.  Result: it would happily return single-digit garbage like "9" from
random noise.

v2 strategy:

1. **Try to find a plate-like rectangle in the image** (geometric heuristic).
2. **Run several preprocessing pipelines** on the candidate region — each
   tuned for a different plate condition (clean / dirty / glare / dim).
3. **Run several Tesseract PSMs** per pipeline.  PSM 7 (single line),
   PSM 8 (single word), and PSM 13 (raw line) are the three that matter
   for plates.
4. **Score every result** using:
     - Tesseract's per-character confidence (`image_to_data`)
     - Whether the text matches a *plausible* plate regex
     - Length sanity
5. **Pick the highest-scoring candidate**.
6. **Reject** anything below a hard floor — better to fail loudly than to
   return junk.

This is a pure-Python pipeline; no GPU, no extra models.  Good enough for an
FYP demo and dramatically better than v1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
import pytesseract
from django.conf import settings

# Allow Windows users to override the Tesseract binary location via .env
if getattr(settings, "TESSERACT_CMD", ""):
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


_PLATE_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"

# A "plausible" plate has at least 4 characters, mostly letters+digits,
# and is between 4 and 10 alphanumerics (covers Pakistani, US, UK, etc.).
_PLATE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{3,9}[A-Z0-9]$")
# A stricter regex catches LEA-1234, ABC-123, BFR-9988 style plates.
_STRICT_RE = re.compile(r"^[A-Z]{2,4}[\- ]?\d{2,5}[A-Z0-9]?$")

# PSM modes worth trying for plates.
#  7  = treat image as single line of text
#  8  = treat image as single word
#  13 = raw line. Treat the image as a single text line, bypassing hacks.
_PSM_MODES = (7, 8, 13)


@dataclass
class Candidate:
    text: str          # cleaned plate text
    raw: str           # what Tesseract actually produced
    confidence: float  # 0..100
    psm: int
    pipeline: str
    plausible: bool    # passes _PLATE_RE
    strict: bool       # passes _STRICT_RE


def _read_image(file_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(file_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Make sure it is a valid JPG/PNG.")
    return img


def _clean(text: str) -> str:
    text = (text or "").upper()
    text = re.sub(r"[^A-Z0-9\-]", "", text)
    return text.strip("-")


# ---------------------------------------------------------------------- #
#  Plate localisation (geometric)
# ---------------------------------------------------------------------- #
def _find_plate_region(image: np.ndarray) -> Optional[np.ndarray]:
    """
    Geometric heuristic to crop the plate.  Better than v1 because we:
      - Use morphology to merge plate characters into one blob
      - Score multiple candidates instead of taking the first 4-corner contour
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)

    # Sobel gradient — plates have lots of vertical edges.
    grad_x = cv2.Sobel(gray, cv2.CV_8U, 1, 0, ksize=3)

    # Threshold then close gaps so characters merge into a rectangle.
    _, binary = cv2.threshold(grad_x, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 5))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    h_img, w_img = gray.shape
    best_score = 0.0
    best_box = None
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if h < 12 or w < 50:
            continue
        ratio = w / float(h)
        # Plates usually have aspect ratio ~2.5–6
        if not (1.8 <= ratio <= 7.0):
            continue
        # Don't grab huge regions (likely whole car), don't grab tiny ones.
        area_pct = (w * h) / float(h_img * w_img)
        if area_pct > 0.6 or area_pct < 0.005:
            continue
        # Score = aspect-ratio centrality * area
        ratio_score = 1.0 - abs(ratio - 3.5) / 5.0
        score = ratio_score * (w * h)
        if score > best_score:
            best_score = score
            best_box = (x, y, w, h)

    if best_box is None:
        return None
    x, y, w, h = best_box
    # Pad a little so we don't clip glyphs.
    pad = max(2, h // 8)
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(w_img, x + w + pad)
    y1 = min(h_img, y + h + pad)
    return image[y0:y1, x0:x1]


# ---------------------------------------------------------------------- #
#  Preprocessing pipelines
# ---------------------------------------------------------------------- #
def _pipeline_otsu(gray: np.ndarray) -> np.ndarray:
    """Standard Otsu binarisation."""
    _, t = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return t


def _pipeline_adaptive(gray: np.ndarray) -> np.ndarray:
    """Adaptive threshold — copes with uneven lighting."""
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )


def _pipeline_clahe(gray: np.ndarray) -> np.ndarray:
    """CLAHE (contrast-limited adaptive histogram eq.) + Otsu — handles dim images."""
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
    _, t = cv2.threshold(eq, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return t


def _pipeline_inverted_otsu(gray: np.ndarray) -> np.ndarray:
    """Some plates are dark text on light background, some inverse — try both."""
    _, t = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return t


_PIPELINES = {
    "otsu": _pipeline_otsu,
    "adaptive": _pipeline_adaptive,
    "clahe": _pipeline_clahe,
    "inv_otsu": _pipeline_inverted_otsu,
}


def _prepare(crop: np.ndarray, pipeline_fn) -> np.ndarray:
    """Resize, denoise, run pipeline, return a binary image ready for OCR."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    # Up-scale small crops — Tesseract loves bigger glyphs.
    h, w = gray.shape[:2]
    if h < 60:
        scale = 60.0 / h
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    return pipeline_fn(gray)


# ---------------------------------------------------------------------- #
#  OCR + scoring
# ---------------------------------------------------------------------- #
def _ocr(img: np.ndarray, psm: int) -> tuple[str, float]:
    """
    Run Tesseract and return (text, mean_confidence_0_100).
    image_to_data gives per-word confidences; we average non-empty words.
    """
    config = f"--psm {psm} --oem 3 -c tessedit_char_whitelist={_PLATE_WHITELIST}"
    try:
        data = pytesseract.image_to_data(
            img, config=config, output_type=pytesseract.Output.DICT
        )
    except Exception:
        return "", 0.0

    parts: list[str] = []
    confs: list[float] = []
    for txt, conf in zip(data.get("text", []), data.get("conf", [])):
        if not txt or not txt.strip():
            continue
        try:
            c = float(conf)
        except (TypeError, ValueError):
            continue
        if c < 0:  # Tesseract returns -1 for skipped words
            continue
        parts.append(txt.strip())
        confs.append(c)

    raw = "".join(parts)
    mean_conf = float(np.mean(confs)) if confs else 0.0
    return raw, mean_conf


def _score(c: Candidate) -> float:
    """Combine length, regex match, and Tesseract confidence into a single score."""
    base = c.confidence  # 0..100
    if c.strict:
        base += 40
    elif c.plausible:
        base += 15
    if 5 <= len(c.text) <= 9:
        base += 5
    return base


def recognize_plate(file_bytes: bytes) -> dict:
    """
    Returns:
        plate_number   string ("" if none plausible)
        confidence     "high" | "medium" | "low" | "none"
        raw_text       what tesseract returned for the winner
        found_plate    True if a plate-shaped region was successfully cropped
        candidates     [{text, score, ...}]   for debugging / UI
    """
    image = _read_image(file_bytes)
    crop = _find_plate_region(image)
    found_plate = crop is not None
    target = crop if crop is not None else image

    candidates: list[Candidate] = []
    for pname, pfn in _PIPELINES.items():
        try:
            prepped = _prepare(target, pfn)
        except Exception:
            continue
        for psm in _PSM_MODES:
            raw, conf = _ocr(prepped, psm)
            cleaned = _clean(raw)
            if not cleaned:
                continue
            cand = Candidate(
                text=cleaned,
                raw=raw,
                confidence=conf,
                psm=psm,
                pipeline=pname,
                plausible=bool(_PLATE_RE.match(cleaned)),
                strict=bool(_STRICT_RE.match(cleaned)),
            )
            candidates.append(cand)

    # Sort by total score, descending.
    candidates.sort(key=_score, reverse=True)

    if not candidates:
        return {
            "plate_number": "",
            "confidence": "none",
            "raw_text": "",
            "found_plate": found_plate,
            "candidates": [],
        }

    winner = candidates[0]
    score = _score(winner)

    # Hard floor — refuse to return obvious garbage.
    if not winner.plausible or len(winner.text) < 4:
        plate_text = ""
        confidence = "none"
    elif winner.strict and winner.confidence >= 70:
        plate_text = winner.text
        confidence = "high"
    elif winner.strict or winner.confidence >= 60:
        plate_text = winner.text
        confidence = "medium"
    else:
        plate_text = winner.text
        confidence = "low"

    return {
        "plate_number": plate_text,
        "confidence": confidence,
        "raw_text": winner.raw,
        "found_plate": found_plate,
        "candidates": [
            {
                "text": c.text,
                "score": round(_score(c), 1),
                "tess_conf": round(c.confidence, 1),
                "pipeline": c.pipeline,
                "psm": c.psm,
            }
            for c in candidates[:5]
        ],
    }


def encode_crop_as_png(file_bytes: bytes) -> Optional[bytes]:
    image = _read_image(file_bytes)
    crop = _find_plate_region(image)
    if crop is None:
        return None
    ok, buf = cv2.imencode(".png", crop)
    return buf.tobytes() if ok else None
