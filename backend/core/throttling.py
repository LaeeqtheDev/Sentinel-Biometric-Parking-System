"""
Per-endpoint rate limits (rates in settings.REST_FRAMEWORK).

Keyed by user id when authenticated, else client IP. Counters live in the
shared Redis cache, so limits hold across every API instance.
"""

from rest_framework.throttling import SimpleRateThrottle


class _ScopedThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        ident = user.pk if user is not None and user.is_authenticated else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class LoginThrottle(_ScopedThrottle):
    scope = "login"

    def get_cache_key(self, request, view):  # always per-IP: user is anonymous here
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class RegisterThrottle(LoginThrottle):
    scope = "register"


class PasskeyThrottle(_ScopedThrottle):
    scope = "passkey"


class GateThrottle(_ScopedThrottle):
    scope = "gate"


class CameraThrottle(_ScopedThrottle):
    scope = "camera"
