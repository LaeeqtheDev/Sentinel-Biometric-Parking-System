"""Celery tasks for the `recognition` queue (see recognition/service.py)."""

import base64

from celery import shared_task


@shared_task(name="recognition.tasks.ocr_plate", time_limit=30, soft_time_limit=25)
def ocr_plate(image_b64: str, fast: bool = False) -> dict:
    from .plate_ocr import recognize_plate

    return recognize_plate(base64.b64decode(image_b64), fast=fast)


@shared_task(name="recognition.tasks.encode_face", time_limit=30, soft_time_limit=25)
def encode_face_task(image_b64: str):
    from .face_engine import encode_face_vector

    return encode_face_vector(base64.b64decode(image_b64))

