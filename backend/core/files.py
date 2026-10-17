"""
Private media delivery.

Media in this system is sensitive: CNIC scans, driving licences, face
reference photos and gate snapshots. The old setup exposed everything under
a guessable public /media/ path (and only served it at all when DEBUG was on).

Now every file is referenced by a short-lived signed URL:

    /api/files/<signed-token>/

The token embeds the storage path and is signed with SECRET_KEY, so it
cannot be forged or edited, and it expires after SIGNED_FILE_URL_TTL_SECONDS.
Serializers emit these URLs only to users who are allowed to see the file,
so a plain <a href> or <img src> works in the browser without exposing the
bucket or the JWT.
"""

from __future__ import annotations

import mimetypes

from django.conf import settings
from django.core import signing
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.urls import reverse
from rest_framework import serializers

_SALT = "sentinel.files"


def sign_path(path: str) -> str:
    return signing.dumps(path, salt=_SALT, compress=True)


def unsign_path(token: str) -> str | None:
    try:
        return signing.loads(
            token, salt=_SALT, max_age=settings.SIGNED_FILE_URL_TTL_SECONDS
        )
    except signing.BadSignature:
        return None


def signed_url(field_file, request=None) -> str | None:
    """Absolute signed URL for a FieldFile, or None when empty."""
    if not field_file:
        return None
    name = getattr(field_file, "name", None) or str(field_file)
    if not name:
        return None
    rel = reverse("signed_file", kwargs={"token": sign_path(name)})
    if request is not None:
        return request.build_absolute_uri(rel)
    return settings.BACKEND_BASE_URL.rstrip("/") + rel


def serve_signed_file(request, token: str):
    """Stream a file referenced by a valid, unexpired signed token."""
    path = unsign_path(token)
    if not path or ".." in path or path.startswith("/"):
        raise Http404
    if not default_storage.exists(path):
        raise Http404
    content_type, _ = mimetypes.guess_type(path)
    resp = FileResponse(
        default_storage.open(path, "rb"),
        content_type=content_type or "application/octet-stream",
    )
    resp["Cache-Control"] = "private, max-age=300"
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
    return resp


class SignedFileField(serializers.Field):
    """Read-only serializer field that renders a FieldFile as a signed URL."""

    def __init__(self, **kwargs):
        kwargs["read_only"] = True
        super().__init__(**kwargs)

    def to_representation(self, value):
        return signed_url(value, self.context.get("request"))
