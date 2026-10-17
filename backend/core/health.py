"""
Health endpoints for load balancers and orchestrators.

/healthz  liveness: the process is up (no dependencies touched).
/readyz   readiness: database and cache both answer; take the instance out
          of rotation otherwise.
"""

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


def healthz(request):
    return JsonResponse({"status": "ok"})


def readyz(request):
    checks = {}
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc.__class__.__name__}"
    try:
        cache.set("readyz", "1", 5)
        checks["cache"] = "ok" if cache.get("readyz") == "1" else "error"
    except Exception as exc:  # noqa: BLE001
        checks["cache"] = f"error: {exc.__class__.__name__}"
    ok = all(v == "ok" for v in checks.values())
    return JsonResponse({"status": "ok" if ok else "degraded", **checks}, status=200 if ok else 503)
