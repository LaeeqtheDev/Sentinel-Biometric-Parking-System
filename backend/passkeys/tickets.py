"""
Single-use passkey tickets.

THE BUG THIS FIXES
------------------
Previously the browser ran a passkey check, got back `{matched, user_id}`,
and then sent `webauthn_user_id=<id>` to /access/verify-exit/. The gate
endpoint trusted that number. Any logged-in driver could therefore POST
`{plate_number: "<someone else's car>", webauthn_user_id: <owner's id>}`
and the gate would open: no passkey was ever involved in that request.

NOW
---
A successful assertion returns an opaque `passkey_ticket`:
  * signed with SECRET_KEY (cannot be forged or edited),
  * bound to the user who actually passed the passkey check,
  * valid for PASSKEY_TICKET_TTL_SECONDS (default 60 s),
  * redeemable exactly once (nonce stored in the shared cache and deleted
    atomically on first use, so it can't be replayed even across workers).

The gate endpoints accept only this ticket as proof of passkey identity.
"""

from __future__ import annotations

import secrets

from django.conf import settings
from django.core import signing
from django.core.cache import cache

_SALT = "sentinel.passkey-ticket"


def issue_ticket(user_id: int) -> str:
    nonce = secrets.token_urlsafe(16)
    ttl = settings.PASSKEY_TICKET_TTL_SECONDS
    cache.set(f"pkt:{nonce}", user_id, ttl)
    return signing.dumps({"u": user_id, "n": nonce}, salt=_SALT)


def redeem_ticket(ticket: str | None) -> int | None:
    """Return the user id the ticket was issued to, consuming it. None if invalid."""
    if not ticket or not isinstance(ticket, str):
        return None
    try:
        data = signing.loads(
            ticket, salt=_SALT, max_age=settings.PASSKEY_TICKET_TTL_SECONDS
        )
    except signing.BadSignature:
        return None
    nonce, user_id = data.get("n"), data.get("u")
    if not nonce or not user_id:
        return None
    key = f"pkt:{nonce}"
    if cache.get(key) != user_id:
        return None
    # delete() is atomic; only the first caller gets a truthy result.
    if not cache.delete(key):
        return None
    return int(user_id)
