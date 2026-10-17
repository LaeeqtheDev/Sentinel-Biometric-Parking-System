"""
Parking session endpoints.

* GET /api/parking/sessions/         All sessions (admin) – ?status=PARKED filters
* GET /api/parking/sessions/active/  Currently parked (admin)
* GET /api/parking/my/               Sessions for vehicles linked to current user
* GET /api/parking/active-for/<plate>/  Is this plate currently inside? (used during exit)
"""

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminRole, is_admin
from vehicles.models import Vehicle, assignments_prefetch, fuzzy_find_vehicle

from .models import ParkingSession
from .serializers import ParkingSessionSerializer
from .services import occupancy


def _session_qs():
    """Everything the nested session serializer touches, preloaded."""
    return ParkingSession.objects.select_related(
        "vehicle",
        "entry_user__biometric",
        "exit_user__biometric",
        "entry_log__vehicle",
        "entry_log__user__biometric",
        "exit_log__vehicle",
        "exit_log__user__biometric",
    ).prefetch_related(
        assignments_prefetch("vehicle__"),
        assignments_prefetch("entry_log__vehicle__"),
        assignments_prefetch("exit_log__vehicle__"),
    )


class ParkingSessionList(generics.ListAPIView):
    serializer_class = ParkingSessionSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = _session_qs()
        s = self.request.query_params.get("status")
        if s:
            qs = qs.filter(status=s.upper())
        plate = self.request.query_params.get("plate")
        if plate:
            qs = qs.filter(vehicle__plate_number__icontains=plate.upper())
        return qs


@api_view(["GET"])
@permission_classes([IsAdminRole])
def active_sessions(request):
    qs = _session_qs().filter(status=ParkingSession.Status.PARKED)[:500]
    return Response(ParkingSessionSerializer(qs, many=True, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def lot_occupancy(request):
    """Spots occupied / capacity / available."""
    return Response(occupancy())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_sessions(request):
    """Sessions for vehicles the current user is an APPROVED user of (latest 200)."""
    qs = _session_qs().filter(
        vehicle__uservehicle__user=request.user,
        vehicle__uservehicle__approved=True,
    ).distinct()[:200]
    return Response(ParkingSessionSerializer(qs, many=True, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def active_for_plate(request, plate: str):
    vehicle = fuzzy_find_vehicle(plate)
    # Drivers can only ask about their own cars (was: anyone, any plate,
    # which revealed whether a given car was currently parked here).
    if not vehicle or (not is_admin(request.user) and not vehicle.is_authorized_user(request.user)):
        return Response({"detail": "Vehicle not found.", "plate": plate}, status=404)
    session = _session_qs().filter(vehicle=vehicle, status=ParkingSession.Status.PARKED).first()
    if not session:
        return Response(
            {"detail": "No active session for this plate.", "plate": plate},
            status=404,
        )
    return Response(ParkingSessionSerializer(session, context={"request": request}).data)
