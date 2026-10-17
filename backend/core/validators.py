"""Upload validation for identity / registration documents."""

import os

from django.conf import settings
from rest_framework.exceptions import ValidationError

ALLOWED_DOC_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
_MAGIC = {
    b"%PDF": ".pdf",
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG": ".png",
    b"RIFF": ".webp",
}


def validate_document(upload, field: str = "file"):
    """Reject oversized files and anything that isn't really a PDF/image."""
    if upload.size > settings.MAX_DOCUMENT_BYTES:
        mb = settings.MAX_DOCUMENT_BYTES // (1024 * 1024)
        raise ValidationError({field: f"File too large (max {mb} MB)."})
    ext = os.path.splitext(upload.name or "")[1].lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        raise ValidationError({field: "Only PDF, JPG, PNG or WEBP files are accepted."})
    head = upload.read(8)
    upload.seek(0)
    if not any(head.startswith(sig) for sig in _MAGIC):
        raise ValidationError({field: "File content does not match a PDF or image."})
    return upload
