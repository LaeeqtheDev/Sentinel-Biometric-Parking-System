"""
Face Recognition Engine
=======================

Wraps the `face_recognition` library (built on dlib) so the rest of the app
can call two clean functions:

    encode_face(image_bytes)   -> bytes (128-d vector serialised)
    verify_face(image_bytes, stored_encoding) -> dict

Why bytes?
    Storing a numpy float64 array of length 128 as raw bytes (1024 B) is
    significantly smaller than JSON-encoding it and works perfectly with
    Django's BinaryField.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from django.conf import settings

# face_recognition pulls in dlib; both must be installed.  See README.
import face_recognition           # type: ignore


# ---------------------------------------------------------------------- #
#  Helpers
# ---------------------------------------------------------------------- #
def _load_image(file_bytes: bytes) -> np.ndarray:
    """face_recognition expects an RGB numpy array."""
    import io
    from PIL import Image

    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    return np.array(img)


def encoding_to_bytes(encoding: np.ndarray) -> bytes:
    return encoding.astype(np.float64).tobytes()


def bytes_to_encoding(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float64)


# ---------------------------------------------------------------------- #
#  Public API
# ---------------------------------------------------------------------- #
def encode_face(file_bytes: bytes) -> Optional[bytes]:
    """
    Detect the (single) most prominent face in an image and return its 128-d
    encoding as raw bytes ready for the database.  Returns None if no face is
    detected.
    """
    image = _load_image(file_bytes)
    locations = face_recognition.face_locations(image, model="hog")
    if not locations:
        return None

    # Use the largest detected face.
    locations.sort(key=lambda r: (r[2] - r[0]) * (r[1] - r[3]), reverse=True)
    encodings = face_recognition.face_encodings(image, [locations[0]])
    if not encodings:
        return None
    return encoding_to_bytes(encodings[0])


def verify_face(file_bytes: bytes, stored_encoding_bytes: bytes) -> dict:
    """
    Compare a freshly-captured face against a stored encoding.

    Returns
    -------
    {
        "matched":  bool,
        "distance": float,         # 0 = identical, ~0.6 = match cutoff
        "found_face": bool
    }
    """
    image = _load_image(file_bytes)
    locations = face_recognition.face_locations(image, model="hog")
    if not locations:
        return {"matched": False, "distance": 1.0, "found_face": False}

    locations.sort(key=lambda r: (r[2] - r[0]) * (r[1] - r[3]), reverse=True)
    encodings = face_recognition.face_encodings(image, [locations[0]])
    if not encodings:
        return {"matched": False, "distance": 1.0, "found_face": False}

    stored = bytes_to_encoding(stored_encoding_bytes)
    distance = float(np.linalg.norm(stored - encodings[0]))
    tolerance = float(getattr(settings, "FACE_MATCH_TOLERANCE", 0.6))

    return {
        "matched": distance <= tolerance,
        "distance": round(distance, 4),
        "found_face": True,
    }
