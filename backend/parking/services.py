"""
Gate state transitions: the ONLY place a ParkingSession is opened or closed.

Before this module, five different code paths (manual verify, live camera,
autonomous mode, admin override, QR pickup) each did their own
"check for active session, then create one" with no transaction and no
lock. Two frames of the same car processed by two workers at once could
both pass the check; the second then crashed with an IntegrityError (500)
or, on the exit side, two exits could both "close" the same session.

Every path now goes through `admit()` / `release()`, which:
  * run in a transaction,
  * lock the vehicle row (SELECT ... FOR UPDATE) so events for one car are
    strictly serialised across every API instance,
  * enforce lot capacity under a lock so two cars can't take the last spot,
  * write the GRANTED AccessLog and the session change atomically, so the
    database and the physical lot can't disagree.

On a denial they raise GateDenied; the caller records a DENIED log.
"""

from __future__ import annotations

from typing import Callable

from django.db import IntegrityError, transaction

from access.models import AccessLog
from vehicles.models import Vehicle

from .models import ParkingSession, PolicyConfig

MakeLog = Callable[[str, str], AccessLog]  # (decision, reason) -> AccessLog


class GateDenied(Exception):
    def __init__(self, reason: str, code: str):
        super().__init__(reason)
        self.reason = reason
        self.code = code


def occupancy() -> dict:
    cfg = PolicyConfig.current()
    occupied = ParkingSession.objects.filter(status=ParkingSession.Status.PARKED).count()
    return {
        "occupied": occupied,
        "capacity": cfg.capacity or None,
        "available": (cfg.capacity - occupied) if cfg.capacity else None,
    }


def admit(
    vehicle: Vehicle,
    *,
    user,
    make_log: MakeLog,
    reason: str,
) -> tuple[AccessLog, ParkingSession]:
    """Grant ENTRY: open a session for `vehicle` or raise GateDenied."""
    with transaction.atomic():
        Vehicle.objects.select_for_update().get(pk=vehicle.pk)

        if ParkingSession.objects.filter(
            vehicle=vehicle, status=ParkingSession.Status.PARKED
        ).exists():
            raise GateDenied("Duplicate entry: vehicle is already parked.", "duplicate")

        cfg = PolicyConfig.current()
        if cfg.capacity:
            # Serialise capacity checks across all entries.
            PolicyConfig.objects.select_for_update().filter(pk=1).first()
            occupied = ParkingSession.objects.filter(
                status=ParkingSession.Status.PARKED
            ).count()
            if occupied >= cfg.capacity:
                raise GateDenied(
                    f"Lot is full ({occupied}/{cfg.capacity} spots occupied).", "full"
                )

        log = make_log(AccessLog.Decision.GRANTED, reason)
        try:
            with transaction.atomic():
                session = ParkingSession.objects.create(
                    vehicle=vehicle, entry_user=user, entry_log=log
                )
        except IntegrityError as exc:  # DB-level unique guard, last line of defence
            raise GateDenied("Duplicate entry: vehicle is already parked.", "duplicate") from exc
        return log, session


def release(
    vehicle: Vehicle,
    *,
    user,
    make_log: MakeLog,
    reason: str,
) -> tuple[AccessLog, ParkingSession]:
    """Grant EXIT: close the active session for `vehicle` or raise GateDenied."""
    with transaction.atomic():
        Vehicle.objects.select_for_update().get(pk=vehicle.pk)
        session = (
            ParkingSession.objects.select_for_update()
            .filter(vehicle=vehicle, status=ParkingSession.Status.PARKED)
            .first()
        )
        if not session:
            raise GateDenied(
                "No active parking session for this vehicle (was it ever parked?).",
                "no_session",
            )
        log = make_log(AccessLog.Decision.GRANTED, reason)
        session.close(exit_user=user, exit_log=log)
        return log, session
