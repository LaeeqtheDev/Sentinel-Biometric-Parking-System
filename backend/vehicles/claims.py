"""
Driver self-service vehicle claims (used by sign-up and "add my vehicle").

Old behaviour (unsafe): claiming a plate that already existed linked the
claimant to it immediately and flipped the *owner's* car to UNDER_REVIEW.
So anyone could (a) attach themselves to a stranger's car, then unlock its
exit with their own passkey, and (b) knock a legitimate car out of service
just by typing its plate.

New behaviour:
  * New plate   -> vehicle created UNDER_REVIEW, claimant linked as OWNER.
                   Approving the vehicle approves the link.
  * Known plate -> claimant gets an UNAPPROVED DRIVER link. Nothing about
                   the existing vehicle changes. The link grants no access
                   until an admin approves it on the approvals page.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction

from .models import UserVehicle, Vehicle, fuzzy_find_vehicle, normalize_plate

VEHICLE_TYPES = {c for c, _ in Vehicle.VehicleType.choices}


def claim_vehicle(user, plate: str, *, make="", model="", color="", vehicle_type="CAR", registration_doc=None) -> dict:
    vt = (vehicle_type or "CAR").upper()
    if vt not in VEHICLE_TYPES:
        vt = "CAR"

    existing = fuzzy_find_vehicle(plate)
    if existing:
        link, created = UserVehicle.objects.get_or_create(
            user=user,
            vehicle=existing,
            defaults={"relationship": UserVehicle.Relationship.DRIVER, "approved": False},
        )
        return {
            "vehicle": existing,
            "link": link,
            "duplicate": True,
            "created": created,
            "message": (
                "This plate is already registered. Your request to be linked to it "
                "is pending admin approval."
                if not link.approved
                else "You are already linked to this vehicle."
            ),
        }

    try:
        with transaction.atomic():
            v = Vehicle.objects.create(
                plate_number=normalize_plate(plate),
                vehicle_type=vt,
                make=(make or "")[:50],
                model=(model or "")[:50],
                color=(color or "")[:30],
                status=Vehicle.Status.UNDER_REVIEW,
            )
            if registration_doc is not None:
                v.registration_doc = registration_doc
                v.save(update_fields=["registration_doc"])
            link = UserVehicle.objects.create(
                user=user, vehicle=v, relationship=UserVehicle.Relationship.OWNER, approved=True
            )
    except IntegrityError:
        # Someone registered the same plate a moment ago: fall back to a claim.
        return claim_vehicle(user, plate, make=make, model=model, color=color, vehicle_type=vt)

    return {
        "vehicle": v,
        "link": link,
        "duplicate": False,
        "created": True,
        "message": "Vehicle added: pending admin approval.",
    }
