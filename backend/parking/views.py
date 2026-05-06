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

from accounts.permissions import IsAdminRole
from vehicles.models import Vehicle, normalize_plate

from .models import ParkingSession
from .serializers import ParkingSessionSerializer


class ParkingSessionList(generics.ListAPIView):
    serializer_class = ParkingSessionSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = ParkingSession.objects.select_related(
            "vehicle", "entry_user", "exit_user", "entry_log", "exit_log"
        ).all()
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
    qs = ParkingSession.objects.filter(
        status=ParkingSession.Status.PARKED
    ).select_related("vehicle", "entry_user")
    return Response(ParkingSessionSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_sessions(request):
    """Sessions where the vehicle is linked to the current user."""
    qs = (
        ParkingSession.objects.filter(vehicle__users=request.user)
        .select_related("vehicle", "entry_user", "exit_user")
        .distinct()
    )
    return Response(ParkingSessionSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def active_for_plate(request, plate: str):
    plate = normalize_plate(plate)
    try:
        vehicle = Vehicle.objects.get(plate_number=plate)
    except Vehicle.DoesNotExist:
        return Response({"detail": "Vehicle not found.", "plate": plate}, status=404)
    session = ParkingSession.active_for(vehicle)
    if not session:
        return Response(
            {"detail": "No active session for this plate.", "plate": plate},
            status=404,
        )
    return Response(ParkingSessionSerializer(session).data)
