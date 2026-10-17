"""
Recognition service: the single entry point for OCR and face work.

WHY
---
Plate OCR (several Tesseract passes, optional EasyOCR) and dlib face
encoding are CPU-bound and take from ~0.5 s to several seconds per image.
They used to run inside the Django request, so a single camera polling every
couple of seconds could pin a gunicorn worker, and a few cameras starved
every other API request (logins, dashboards, the driver app).

Now:
  * RECOGNITION_ASYNC=false (local dev): runs in-process, same as before.
  * RECOGNITION_ASYNC=true (production): the work is sent to Celery workers
    on the `recognition` queue. The API waits up to
    RECOGNITION_TIMEOUT_SECONDS, then returns 503 instead of hanging.
    Recognition capacity scales by adding worker processes/machines,
    independently of the API.

Every image is also checked before decoding: pixel-count bombs are rejected
and oversized frames are downscaled, so CPU cost per frame is bounded.
"""

from __future__ import annotations

import base64
import io
import logging

import numpy as np
from django.conf import settings
from PIL import Image

log = logging.getLogger("sentinel.recognition")


class RecognitionError(Exception):
    """Bad input image (400)."""


class RecognitionUnavailable(Exception):
    """Workers busy / timed out (503)."""


# ---------------------------------------------------------------------- #
#  Input hygiene
# ---------------------------------------------------------------------- #
def prepare_image(img_bytes: bytes) -> bytes:
    """Validate, bound and normalise an uploaded image. Returns JPEG bytes."""
    if not img_bytes:
        raise RecognitionError("Empty image.")
    try:
        with Image.open(io.BytesIO(img_bytes)) as probe:
            w, h = probe.size  # reads the header only, no full decode
            if w * h > settings.MAX_IMAGE_PIXELS:
                raise RecognitionError(f"Image too large ({w}x{h}).")
            probe.load()
            img = probe.convert("RGB")
    except RecognitionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RecognitionError("Could not decode image. Send a valid JPG/PNG.") from exc

    max_w = settings.OCR_MAX_WIDTH
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((max_w, int(img.height * ratio)), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    return out.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _run(task, *args):
    """Dispatch to Celery and wait, or fail fast with RecognitionUnavailable."""
    try:
        return task.apply_async(args=args).get(
            timeout=settings.RECOGNITION_TIMEOUT_SECONDS, disable_sync_subtasks=False
        )
    except Exception as exc:  # noqa: BLE001  (TimeoutError, broker down, ...)
        log.warning("recognition task %s failed: %s", task.name, exc)
        raise RecognitionUnavailable("Recognition workers are busy. Retry shortly.") from exc


# ---------------------------------------------------------------------- #
#  Public API
# ---------------------------------------------------------------------- #
def read_plate(img_bytes: bytes, fast: bool = False) -> dict:
    data = prepare_image(img_bytes)
    if settings.RECOGNITION_ASYNC:
        from .tasks import ocr_plate

        return _run(ocr_plate, _b64(data), fast)
    from .plate_ocr import recognize_plate

    return recognize_plate(data, fast=fast)


def face_encoding(img_bytes: bytes) -> list[float] | None:
    """128-d encoding of the largest face in the image, or None."""
    data = prepare_image(img_bytes)
    if settings.RECOGNITION_ASYNC:
        from .tasks import encode_face_task

        return _run(encode_face_task, _b64(data))
    from .face_engine import encode_face_vector

    return encode_face_vector(data)


def face_available() -> bool:
    from .face_engine import FACE_RECOGNITION_AVAILABLE

    return FACE_RECOGNITION_AVAILABLE or settings.RECOGNITION_ASYNC


def compare(encoding: list[float] | np.ndarray, stored_blob: bytes) -> float:
    stored = np.frombuffer(bytes(stored_blob), dtype=np.float64)
    live = np.asarray(encoding, dtype=np.float64)
    if stored.size != live.size or stored.size == 0:
        return 1.0
    return float(np.linalg.norm(stored - live))


def verify_face(img_bytes: bytes, stored_blob: bytes) -> dict:
    tolerance = float(settings.FACE_MATCH_TOLERANCE)
    if not face_available():
        return {
            "matched": False, "distance": None, "found_face": False, "tolerance": tolerance,
            "reason": "Face recognition is not available on this deployment. Use a passkey.",
        }
    enc = face_encoding(img_bytes)
    if enc is None:
        return {
            "matched": False, "distance": None, "found_face": False, "tolerance": tolerance,
            "reason": "No face detected. Make sure your face is well lit, centred and not too small.",
        }
    dist = compare(enc, stored_blob)
    matched = dist <= tolerance
    return {
        "matched": matched,
        "distance": round(dist, 4),
        "found_face": True,
        "tolerance": tolerance,
        "reason": None if matched else (
            f"Face does not match the enrolled identity (distance {dist:.3f} > {tolerance:.2f})."
        ),
    }


def encode_for_storage(img_bytes: bytes) -> bytes | None:
    """Encoding as raw float64 bytes for BiometricProfile.encoding."""
    enc = face_encoding(img_bytes)
    if enc is None:
        return None
    return np.asarray(enc, dtype=np.float64).tobytes()
