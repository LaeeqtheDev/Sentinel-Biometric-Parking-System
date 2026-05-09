"""
License Plate Recognition Engine — v4
=====================================

Layered OCR strategy:

1. **EasyOCR** (optional, deep-learning based) — used as primary engine
   when the `easyocr` package is installed.  Handles handwritten,
   decorative, multi-line plates that Tesseract cannot.
2. **Tesseract** (always available) — used as fallback or in parallel.
   Multiple preprocessing pipelines × multiple PSMs (single-line, single-
   word, raw line, sparse text) for robustness.
3. **Jurisdiction filter** — discards candidate words like 'PUNJAB',
   'SINDH', 'KPK', 'ICT' so the system doesn't return them as the plate.
4. **Multi-line aware** — when a plate has a jurisdiction header (common
   in Pakistan / India), we collect ALL text, drop jurisdiction words,
   and pick the line that matches plate-shape regex.
5. **Confidence-based selection + hard floor** — refuses to return text
   shorter than 4 chars or that doesn't match a plausible plate pattern.

To enable EasyOCR (HUGE accuracy bump on hard plates):
    pip install easyocr
First run downloads ~64 MB of model weights.
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


# ---------------------------------------------------------------------- #
#  Optional EasyOCR engine (loaded lazily on first call)
# ---------------------------------------------------------------------- #
_EASYOCR_READER = None
_EASYOCR_TRIED = False


def _get_easyocr():
    """Lazy-import EasyOCR.  Returns the reader, or None if not installed."""
    global _EASYOCR_READER, _EASYOCR_TRIED
    if _EASYOCR_TRIED:
        return _EASYOCR_READER
    _EASYOCR_TRIED = True
    try:
        import easyocr  # type: ignore
        # gpu=False forces CPU; set True if user has CUDA
        _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
    except Exception:
        _EASYOCR_READER = None
    return _EASYOCR_READER


_PLATE_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"

# A "plausible" plate has at least 4 characters, mostly letters+digits,
# and is between 4 and 10 alphanumerics (covers PK, IN, US, UK, etc.).
_PLATE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{3,9}[A-Z0-9]$")
# Pakistani plate format: LL(L) NNN(N) — e.g. AAP-1478, LEA-1234, BFR-9988
_STRICT_PK = re.compile(r"^[A-Z]{2,4}[\- ]?\d{2,5}[A-Z0-9]?$")
# A plate that's 100% digits (rare but possible) – relax the regex
_ALL_NUMERIC = re.compile(r"^\d{4,8}$")

# Jurisdiction / region words that show up on plates as headers but ARE
# NOT the plate identifier.  Discard them aggressively.
_JURISDICTION_WORDS = {
    "PUNJAB", "SINDH", "KPK", "BALOCHISTAN", "ICT", "GB", "AJK",
    "PAKISTAN", "ISLAMABAD", "KARACHI", "LAHORE", "QUETTA",
    "PESHAWAR", "FEDERAL", "GOVT", "GOVERNMENT", "NATIONAL",
    "GOV", "PROVINCE",
    # Common decorative words too:
    "TAXI", "RENT", "PRIVATE",
}

# PSM modes worth trying for plates:
#  6  = single uniform block of text (good for 2-line plates seen as a block)
#  7  = single line of text
#  8  = single word
#  11 = sparse text (find as much text as possible, in any order)
#  13 = raw line
_PSM_MODES = (6, 7, 8, 11, 13)


@dataclass
class Candidate:
    text: str          # cleaned plate text
    raw: str           # what the engine actually produced
    confidence: float  # 0..100
    engine: str        # "easyocr" or "tesseract@psmN@..."
    plausible: bool    # passes _PLATE_RE
    strict: bool       # passes _STRICT_PK or _ALL_NUMERIC


# ---------------------------------------------------------------------- #
#  Image helpers
# ---------------------------------------------------------------------- #
def _read_image(file_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(file_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Make sure it is a valid JPG/PNG.")
    return img


def _enhance(image: np.ndarray, scale_factor: float = 2.0) -> np.ndarray:
    """Bicubic upscale + denoise + unsharp mask."""
    h, w = image.shape[:2]
    upscaled = cv2.resize(
        image,
        (int(w * scale_factor), int(h * scale_factor)),
        interpolation=cv2.INTER_CUBIC,
    )
    if upscaled.ndim == 3:
        denoised = cv2.fastNlMeansDenoisingColored(upscaled, None, 7, 7, 7, 21)
    else:
        denoised = cv2.fastNlMeansDenoising(upscaled, None, 7, 7, 21)
    blur = cv2.GaussianBlur(denoised, (0, 0), 2.0)
    return cv2.addWeighted(denoised, 1.5, blur, -0.5, 0)


def _is_blurry(image: np.ndarray, threshold: float = 60.0) -> tuple[bool, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return score < threshold, score


def _deskew(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)
    if lines is None or len(lines) == 0:
        return image
    angles: list[float] = []
    for line in lines[:20]:
        rho, theta = line[0]
        deg = (theta * 180.0 / np.pi) - 90.0
        if -30 < deg < 30:
            angles.append(deg)
    if not angles:
        return image
    angle = float(np.median(angles))
    if abs(angle) < 1.5:
        return image
    h, w = image.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def _clean(text: str) -> str:
    text = (text or "").upper()
    text = re.sub(r"[^A-Z0-9\-]", "", text)
    return text.strip("-")


def _is_jurisdiction(word: str) -> bool:
    """True if a candidate is just a jurisdiction header like 'PUNJAB'."""
    cleaned = re.sub(r"[^A-Z]", "", word.upper())
    return cleaned in _JURISDICTION_WORDS


# ---------------------------------------------------------------------- #
#  Plate region localisation
# ---------------------------------------------------------------------- #
def _find_plate_region(image: np.ndarray) -> Optional[np.ndarray]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    grad_x = cv2.Sobel(gray, cv2.CV_8U, 1, 0, ksize=3)
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
        if not (1.0 <= ratio <= 7.0):  # widened to accept square-ish 2-line plates
            continue
        area_pct = (w * h) / float(h_img * w_img)
        if area_pct > 0.6 or area_pct < 0.005:
            continue
        ratio_score = 1.0 - abs(ratio - 3.0) / 5.0
        score = ratio_score * (w * h)
        if score > best_score:
            best_score = score
            best_box = (x, y, w, h)
    if best_box is None:
        return None
    x, y, w, h = best_box
    pad = max(2, h // 8)
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(w_img, x + w + pad), min(h_img, y + h + pad)
    return image[y0:y1, x0:x1]


# ---------------------------------------------------------------------- #
#  Tesseract preprocessing pipelines
# ---------------------------------------------------------------------- #
def _pipeline_otsu(gray):
    _, t = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return t


def _pipeline_adaptive(gray):
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )


def _pipeline_clahe(gray):
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
    _, t = cv2.threshold(eq, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return t


def _pipeline_inverted_otsu(gray):
    _, t = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return t


_PIPELINES = {
    "otsu": _pipeline_otsu,
    "adaptive": _pipeline_adaptive,
    "clahe": _pipeline_clahe,
    "inv_otsu": _pipeline_inverted_otsu,
}


def _prepare(crop, pipeline_fn):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    h, w = gray.shape[:2]
    if h < 60:
        scale = 60.0 / h
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    return pipeline_fn(gray)


def _ocr_tesseract(img, psm: int) -> tuple[str, float]:
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
        if c < 0:
            continue
        parts.append(txt.strip())
        confs.append(c)
    raw = " ".join(parts)
    mean_conf = float(np.mean(confs)) if confs else 0.0
    return raw, mean_conf


def _ocr_easyocr(image: np.ndarray) -> list[tuple[str, float]]:
    """
    Returns list of (text, confidence_0_100) tuples for every text region
    detected by EasyOCR.  Empty list if EasyOCR isn't installed.
    """
    reader = _get_easyocr()
    if reader is None:
        return []
    try:
        results = reader.readtext(image, detail=1, paragraph=False)
    except Exception:
        return []
    out = []
    for res in results:
        # res is (bbox, text, confidence_0_1)
        if len(res) < 3:
            continue
        text, conf = res[1], res[2]
        out.append((text, float(conf) * 100.0))
    return out


def _score(c: Candidate) -> float:
    base = c.confidence
    if c.strict:
        base += 40
    elif c.plausible:
        base += 15
    if 5 <= len(c.text) <= 9:
        base += 5
    # Penalise jurisdiction words even if they snuck through
    if _is_jurisdiction(c.text):
        base -= 100
    return base


# ---------------------------------------------------------------------- #
#  Multi-line splitter — when OCR returns several words/lines together,
#  split, filter jurisdiction terms, and produce per-line candidates.
# ---------------------------------------------------------------------- #
def _split_into_candidates(raw_text: str, confidence: float, engine: str) -> list[Candidate]:
    """
    Given raw OCR output (possibly containing multiple words/lines), split
    on whitespace, drop jurisdiction words, and try BOTH:
      - each individual word as a candidate
      - the whole concatenated string as a candidate
    """
    candidates: list[Candidate] = []
    if not raw_text or not raw_text.strip():
        return candidates

    # Try each whitespace-separated chunk
    chunks = re.split(r"\s+", raw_text.strip())
    cleaned_chunks = []
    for chunk in chunks:
        if _is_jurisdiction(chunk):
            continue
        cleaned = _clean(chunk)
        if cleaned and len(cleaned) >= 2:
            cleaned_chunks.append(cleaned)
            candidates.append(Candidate(
                text=cleaned,
                raw=chunk,
                confidence=confidence,
                engine=engine,
                plausible=bool(_PLATE_RE.match(cleaned)),
                strict=bool(_STRICT_PK.match(cleaned) or _ALL_NUMERIC.match(cleaned)),
            ))

    # ALSO try joining adjacent chunks ("AAP" + "1478" → "AAP1478", "AAP-1478")
    if len(cleaned_chunks) >= 2:
        for i in range(len(cleaned_chunks) - 1):
            joined = cleaned_chunks[i] + cleaned_chunks[i + 1]
            hyphenated = cleaned_chunks[i] + "-" + cleaned_chunks[i + 1]
            for v in (joined, hyphenated):
                candidates.append(Candidate(
                    text=v,
                    raw=" ".join(cleaned_chunks[i:i + 2]),
                    confidence=confidence,
                    engine=engine + "+joined",
                    plausible=bool(_PLATE_RE.match(v)),
                    strict=bool(_STRICT_PK.match(v) or _ALL_NUMERIC.match(v)),
                ))

    return candidates


# ---------------------------------------------------------------------- #
#  MAIN: recognize_plate
# ---------------------------------------------------------------------- #
def recognize_plate(file_bytes: bytes, fast: bool = False) -> dict:
    """
    Returns:
        plate_number   string ("" if none plausible)
        confidence     "high" | "medium" | "low" | "none"
        raw_text       what the winning engine produced
        engine         "easyocr" | "tesseract" | "none"
        found_plate    True if a plate-shaped region was successfully cropped
        sharpness      Laplacian-variance score
        blurry         True if source frame is too blurry
        candidates     [{text, score, ...}]   for debugging / UI

    `fast=True` (used by live-camera):
        - If EasyOCR is available, runs ONLY EasyOCR (skips all Tesseract).
        - If EasyOCR is missing, runs a limited Tesseract sweep (no rotations,
          just 2 PSMs) instead of the full 100-call sweep.
        - This brings per-frame latency from ~30s to ~1-2s.
    """
    image = _read_image(file_bytes)
    blurry, sharpness = _is_blurry(image, threshold=60.0)

    # Resize huge frames to keep things snappy.  Most webcams give 1280×720
    # which is fine; only resize if larger than that.
    h, w = image.shape[:2]
    if max(h, w) > 1280:
        scale = 1280.0 / max(h, w)
        image = cv2.resize(image, (int(w * scale), int(h * scale)),
                           interpolation=cv2.INTER_AREA)

    # Enhance blurry / very small images.  Skip in fast mode (denoising is
    # expensive — ~500ms on CPU).
    if not fast:
        h, w = image.shape[:2]
        if blurry or max(h, w) < 800:
            try:
                image = _enhance(image, scale_factor=2.0)
            except Exception:
                pass

    image = _deskew(image)
    crop = _find_plate_region(image)
    found_plate = crop is not None
    target = crop if crop is not None else image

    candidates: list[Candidate] = []

    # ===== Pass 1: EasyOCR on the FULL image (it handles localisation) ====
    easy_results = _ocr_easyocr(image)
    if easy_results:
        for text, conf in easy_results:
            candidates.extend(_split_into_candidates(text, conf, "easyocr"))
        if crop is not None and not fast:
            for text, conf in _ocr_easyocr(crop):
                candidates.extend(_split_into_candidates(text, conf, "easyocr_crop"))

    # FAST MODE: if EasyOCR returned a plausible candidate, skip Tesseract entirely.
    has_plausible_easy = any(c.plausible for c in candidates)
    skip_tesseract = fast and has_plausible_easy

    if not skip_tesseract:
        # ===== Pass 2: Tesseract — full sweep in normal mode, light in fast =====
        if fast:
            rotations = [0]
            psms_to_try = (7, 11)
            pipelines_to_try = {"otsu": _PIPELINES["otsu"], "adaptive": _PIPELINES["adaptive"]}
        else:
            rotations = [0, -8, 8, -15, 15] if crop is not None else [0]
            psms_to_try = _PSM_MODES
            pipelines_to_try = _PIPELINES

        for rot_deg in rotations:
            if rot_deg != 0:
                h2, w2 = target.shape[:2]
                M = cv2.getRotationMatrix2D((w2 / 2, h2 / 2), rot_deg, 1.0)
                rotated = cv2.warpAffine(
                    target, M, (w2, h2),
                    flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
                )
            else:
                rotated = target
            for pname, pfn in pipelines_to_try.items():
                try:
                    prepped = _prepare(rotated, pfn)
                except Exception:
                    continue
                for psm in psms_to_try:
                    raw, conf = _ocr_tesseract(prepped, psm)
                    if not raw:
                        continue
                    candidates.extend(
                        _split_into_candidates(raw, conf, f"tesseract@{pname}@psm{psm}@rot{rot_deg}")
                    )

        # ===== Pass 3: whole-image PSM 11 — only run when nothing plausible found yet
        if not fast and not any(c.plausible for c in candidates) and image is not None:
            try:
                full_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
                for pname, pfn in _PIPELINES.items():
                    try:
                        full_prepped = pfn(full_gray)
                    except Exception:
                        continue
                    for psm in (6, 11, 12):
                        raw, conf = _ocr_tesseract(full_prepped, psm)
                        if not raw:
                            continue
                        candidates.extend(
                            _split_into_candidates(raw, conf, f"tesseract@full@{pname}@psm{psm}")
                        )
            except Exception:
                pass

    # Deduplicate candidates by text, keeping highest score
    by_text: dict[str, Candidate] = {}
    for c in candidates:
        existing = by_text.get(c.text)
        if existing is None or _score(c) > _score(existing):
            by_text[c.text] = c
    candidates = list(by_text.values())
    candidates.sort(key=_score, reverse=True)

    if not candidates:
        return {
            "plate_number": "",
            "confidence": "none",
            "raw_text": "",
            "engine": "none",
            "found_plate": found_plate,
            "sharpness": round(sharpness, 1),
            "blurry": blurry,
            "easyocr_available": _get_easyocr() is not None,
            "candidates": [],
        }

    winner = candidates[0]

    # Hard floor — refuse to return obvious garbage (less than 4 alphanumerics
    # OR no plausible plate-shape match anywhere in the candidate list).
    has_any_plausible = any(c.plausible for c in candidates)
    if len(winner.text) < 4:
        plate_text = ""
        confidence = "none"
    elif winner.plausible and winner.strict and winner.confidence >= 70:
        plate_text = winner.text
        confidence = "high"
    elif winner.plausible and (winner.strict or winner.confidence >= 55):
        plate_text = winner.text
        confidence = "medium"
    elif winner.plausible:
        plate_text = winner.text
        confidence = "low"
    elif has_any_plausible:
        # Winner wasn't plausible but a later candidate is — return that
        for c in candidates:
            if c.plausible and len(c.text) >= 4:
                winner = c
                plate_text = c.text
                confidence = "low"
                break
        else:
            plate_text = ""
            confidence = "none"
    else:
        # Nothing plausible — return the longest >=4-char text as low-confidence
        # so the admin can still see what OCR "saw" and correct it.
        for c in candidates:
            if len(c.text) >= 4:
                plate_text = c.text
                confidence = "low"
                winner = c
                break
        else:
            plate_text = ""
            confidence = "none"

    if blurry and confidence == "high":
        confidence = "medium"
    elif blurry and confidence == "medium":
        confidence = "low"

    return {
        "plate_number": plate_text,
        "confidence": confidence,
        "raw_text": winner.raw,
        "engine": winner.engine.split("@")[0],  # "easyocr" or "tesseract"
        "found_plate": found_plate,
        "sharpness": round(sharpness, 1),
        "blurry": blurry,
        "easyocr_available": _get_easyocr() is not None,
        "candidates": [
            {
                "text": c.text,
                "score": round(_score(c), 1),
                "tess_conf": round(c.confidence, 1),
                "engine": c.engine,
            }
            for c in candidates[:8]
        ],
    }


def encode_crop_as_png(file_bytes: bytes) -> Optional[bytes]:
    image = _read_image(file_bytes)
    crop = _find_plate_region(image)
    if crop is None:
        return None
    ok, buf = cv2.imencode(".png", crop)
    return buf.tobytes() if ok else None
