"""
Policy config endpoints — admin-only.

GET  /api/parking/policy/   Read current policy
POST /api/parking/policy/   Update policy (full or partial)
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsAdminRole

from .models import PolicyConfig


_FIELDS = (
    "trusted_threshold",
    "normal_threshold",
    "peak_start",
    "peak_end",
    "peak_enabled",
    "autonomous_mode",
    "force_biometric_during_peak",
    "auto_entry_for_trusted",
    "ocr_min_confidence_normal",
    "ocr_min_confidence_peak",
    "risk_low_max",
    "risk_medium_max",
)


def _serialize(cfg: PolicyConfig) -> dict:
    return {
        "trusted_threshold": cfg.trusted_threshold,
        "normal_threshold": cfg.normal_threshold,
        "peak_start": cfg.peak_start.strftime("%H:%M"),
        "peak_end": cfg.peak_end.strftime("%H:%M"),
        "peak_enabled": cfg.peak_enabled,
        "is_peak_now": cfg.is_peak_now(),
        "autonomous_mode": cfg.autonomous_mode,
        "force_biometric_during_peak": cfg.force_biometric_during_peak,
        "auto_entry_for_trusted": cfg.auto_entry_for_trusted,
        "ocr_min_confidence_normal": cfg.ocr_min_confidence_normal,
        "ocr_min_confidence_peak": cfg.ocr_min_confidence_peak,
        "risk_low_max": cfg.risk_low_max,
        "risk_medium_max": cfg.risk_medium_max,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@api_view(["GET", "POST", "PATCH"])
@permission_classes([IsAdminRole])
def policy_config(request):
    cfg = PolicyConfig.current()
    if request.method == "GET":
        return Response(_serialize(cfg))

    # POST/PATCH — partial update
    data = request.data
    for f in _FIELDS:
        if f not in data:
            continue
        val = data[f]
        if f in ("peak_start", "peak_end") and isinstance(val, str):
            from datetime import time
            try:
                hh, mm = val.split(":")
                val = time(int(hh), int(mm))
            except Exception:
                return Response({"detail": f"Invalid time format for {f}: HH:MM expected."}, status=400)
        setattr(cfg, f, val)
    cfg.updated_by = request.user if request.user.is_authenticated else None
    cfg.save()
    return Response(_serialize(cfg))
