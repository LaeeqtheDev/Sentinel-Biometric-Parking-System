"""
Regression tests for the security and scaling fixes.

Run:  DEBUG=True python manage.py test
"""

from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from access.models import AccessLog, Incident
from accounts.models import User
from core.files import sign_path
from parking.models import ParkingSession, PolicyConfig
from parking.pricing import compute_fee
from parking.services import GateDenied, admit
from passkeys.models import PickupToken
from passkeys.tickets import issue_ticket, redeem_ticket
from vehicles.models import UserVehicle, Vehicle, fuzzy_find_vehicle


def _ocr(plate, confidence="high"):
    return {
        "plate_number": plate, "confidence": confidence, "raw_text": plate,
        "found_plate": True, "engine": "test", "candidates": [],
    }


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("admin", password="x-Strong-Pass-1", role="ADMIN")
        self.owner = User.objects.create_user("owner", password="x-Strong-Pass-1", role="DRIVER")
        self.thief = User.objects.create_user("thief", password="x-Strong-Pass-1", role="DRIVER")
        self.car = Vehicle.objects.create(plate_number="AAP-1478", status=Vehicle.Status.ACTIVE)
        UserVehicle.objects.create(user=self.owner, vehicle=self.car, relationship="OWNER", approved=True)

    def client_for(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def park(self, vehicle=None):
        vehicle = vehicle or self.car
        return ParkingSession.objects.create(vehicle=vehicle, entry_user=self.owner)


class PlateLookupTests(Base):
    def test_fuzzy_lookup_uses_canonical_column(self):
        self.assertEqual(self.car.plate_canonical, "AAP1478")
        for variant in ("aap 1478", "AAP_1478", "AAP1478", "aap-1478"):
            self.assertEqual(fuzzy_find_vehicle(variant), self.car)
        with self.assertNumQueries(1):
            fuzzy_find_vehicle("AAP 1478")


class GateSecurityTests(Base):
    def test_driver_cannot_open_someone_elses_car_with_user_id(self):
        """The original exploit: client-supplied webauthn_user_id."""
        self.park()
        res = self.client_for(self.thief).post(
            "/api/access/verify-exit/",
            {"plate_number": "AAP1478", "webauthn_user_id": self.owner.id},
            format="json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertTrue(ParkingSession.objects.filter(vehicle=self.car, status="PARKED").exists())

    def test_owner_id_without_ticket_is_rejected_even_for_owner(self):
        self.park()
        res = self.client_for(self.owner).post(
            "/api/access/verify-exit/",
            {"plate_number": "AAP1478", "webauthn_user_id": self.owner.id},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["decision"], "DENIED")
        self.assertIn("passkey_ticket", res.data.get("passkey_error", ""))

    def test_owner_exits_with_valid_ticket_and_gets_fee(self):
        self.park()
        res = self.client_for(self.owner).post(
            "/api/access/verify-exit/",
            {"plate_number": "AAP1478", "passkey_ticket": issue_ticket(self.owner.id)},
            format="json",
        )
        self.assertEqual(res.data["decision"], "GRANTED", res.data)
        self.assertIn("fee", res.data)
        self.assertFalse(ParkingSession.objects.filter(vehicle=self.car, status="PARKED").exists())

    def test_ticket_is_single_use(self):
        t = issue_ticket(self.owner.id)
        self.assertEqual(redeem_ticket(t), self.owner.id)
        self.assertIsNone(redeem_ticket(t))
        self.assertIsNone(redeem_ticket(t[:-2] + "xx"))

    def test_driver_cannot_use_another_users_ticket(self):
        UserVehicle.objects.create(user=self.thief, vehicle=self.car, relationship="DRIVER", approved=True)
        self.park()
        res = self.client_for(self.thief).post(
            "/api/access/verify-exit/",
            {"plate_number": "AAP1478", "passkey_ticket": issue_ticket(self.owner.id)},
            format="json",
        )
        self.assertEqual(res.data["decision"], "DENIED")

    def test_admin_override_flag_ignored_for_drivers_and_false_string(self):
        walkin = User.objects.create_user("walkin", password="x-Strong-Pass-1")
        UserVehicle.objects.create(user=walkin, vehicle=self.car, relationship="OWNER", approved=True)
        UserVehicle.objects.filter(user=self.owner).delete()
        res = self.client_for(walkin).post(
            "/api/access/verify-entry/",
            {"plate_number": "AAP1478", "admin_override": True},
            format="json",
        )
        self.assertEqual(res.data["decision"], "DENIED")
        res = self.client_for(self.admin).post(
            "/api/access/verify-entry/",
            {"plate_number": "AAP1478", "admin_override": "false"},
            format="json",
        )
        self.assertEqual(res.data["decision"], "DENIED")
        res = self.client_for(self.admin).post(
            "/api/access/verify-entry/",
            {"plate_number": "AAP1478", "admin_override": "true"},
            format="json",
        )
        self.assertEqual(res.data["decision"], "GRANTED", res.data)


class ClaimTests(Base):
    def test_claiming_existing_plate_creates_pending_link_only(self):
        res = self.client_for(self.thief).post(
            "/api/vehicles/my/add/", {"plate_number": "aap 1478"}, format="json"
        )
        self.assertEqual(res.status_code, 201)
        self.assertFalse(res.data["link_approved"])
        self.car.refresh_from_db()
        self.assertEqual(self.car.status, Vehicle.Status.ACTIVE)  # owner unaffected
        self.assertFalse(self.car.is_authorized_user(self.thief))
        self.park()
        res = self.client_for(self.thief).post(
            "/api/access/verify-exit/", {"plate_number": "AAP1478"}, format="json"
        )
        self.assertEqual(res.status_code, 403)

    def test_admin_can_approve_claim(self):
        self.client_for(self.thief).post("/api/vehicles/my/add/", {"plate_number": "AAP1478"}, format="json")
        claims = self.client_for(self.admin).get("/api/vehicles/pending-claims/").data
        self.assertEqual(len(claims), 1)
        url = f"/api/vehicles/{self.car.id}/assignments/{claims[0]['id']}/approve/"
        self.assertEqual(self.client_for(self.admin).post(url).status_code, 200)
        self.assertTrue(self.car.is_authorized_user(self.thief))

    def test_owner_can_add_driver(self):
        res = self.client_for(self.owner).post(
            f"/api/vehicles/my/{self.car.id}/drivers/", {"username": "thief"}, format="json"
        )
        self.assertEqual(res.status_code, 201)
        res = self.client_for(self.thief).post(
            f"/api/vehicles/my/{self.car.id}/drivers/", {"username": "admin"}, format="json"
        )
        self.assertEqual(res.status_code, 403)


class SessionIntegrityTests(Base):
    def _make_log(self, decision, reason):
        return AccessLog.objects.create(
            event_type="ENTRY", plate_detected=self.car.plate_number, vehicle=self.car,
            status=decision, reason=reason,
        )

    def test_duplicate_entry_is_denied_not_500(self):
        admit(self.car, user=self.owner, make_log=self._make_log, reason="ok")
        with self.assertRaises(GateDenied) as ctx:
            admit(self.car, user=self.owner, make_log=self._make_log, reason="ok")
        self.assertEqual(ctx.exception.code, "duplicate")
        self.assertEqual(ParkingSession.objects.filter(status="PARKED").count(), 1)

    def test_capacity_is_enforced(self):
        cfg = PolicyConfig.objects.get_or_create(pk=1)[0]
        cfg.capacity = 1
        cfg.save()
        other = Vehicle.objects.create(plate_number="LEA-1234")
        admit(self.car, user=self.owner, make_log=self._make_log, reason="ok")
        with self.assertRaises(GateDenied) as ctx:
            admit(other, user=None, make_log=self._make_log, reason="ok")
        self.assertEqual(ctx.exception.code, "full")


class PricingTests(TestCase):
    def test_peak_offpeak_split(self):
        cfg = PolicyConfig(
            peak_enabled=True, peak_start=time(18, 0), peak_end=time(23, 0),
            hourly_rate=Decimal("100"), peak_hourly_rate=Decimal("200"), grace_minutes=10,
            currency="PKR",
        )
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime(2026, 1, 5, 17, 0), tz)
        end = timezone.make_aware(datetime(2026, 1, 5, 19, 0), tz)
        amount, br = compute_fee(start, end, cfg)
        self.assertEqual(br["peak_minutes"], 60.0)
        self.assertEqual(amount, Decimal("300.00"))  # 1h @100 + 1h @200

    def test_grace_period_free(self):
        cfg = PolicyConfig(hourly_rate=Decimal("100"), peak_hourly_rate=Decimal("100"), grace_minutes=10)
        now = timezone.now()
        amount, _ = compute_fee(now, now + timedelta(minutes=5), cfg)
        self.assertEqual(amount, Decimal("0.00"))

    def test_overnight_peak_window(self):
        cfg = PolicyConfig(
            peak_enabled=True, peak_start=time(22, 0), peak_end=time(2, 0),
            hourly_rate=Decimal("0"), peak_hourly_rate=Decimal("60"), grace_minutes=0,
        )
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime(2026, 1, 5, 23, 0), tz)
        end = timezone.make_aware(datetime(2026, 1, 6, 3, 0), tz)
        amount, br = compute_fee(start, end, cfg)
        self.assertEqual(br["peak_minutes"], 180.0)
        self.assertEqual(amount, Decimal("180.00"))


class LiveCameraTests(Base):
    def setUp(self):
        super().setUp()
        User.objects.filter(pk=self.owner.pk).update(trust_score=95, trust_level="TRUSTED")
        cfg = PolicyConfig.objects.get_or_create(pk=1)[0]
        cfg.peak_enabled = False
        cfg.off_hours_start = time(3, 0)
        cfg.off_hours_end = time(3, 1)
        cfg.save()

    @mock.patch("recognition.service.read_plate", return_value=_ocr("AAP1478"))
    def test_autonomous_entry_once_per_debounce_window(self, _):
        c = self.client_for(self.admin)
        r1 = c.post("/api/access/live-detect/", {"plate_image_base64": "eA=="}, format="json")
        self.assertTrue(r1.data.get("auto_granted"), r1.data)
        r2 = c.post("/api/access/live-detect/", {"plate_image_base64": "eA=="}, format="json")
        self.assertFalse(r2.data.get("auto_granted", False))
        self.assertEqual(ParkingSession.objects.filter(vehicle=self.car).count(), 1)

    @mock.patch("recognition.service.read_plate", return_value=_ocr("AAP1478"))
    def test_policy_switch_disables_autonomous(self, _):
        cfg = PolicyConfig.objects.get(pk=1)
        cfg.autonomous_mode = False
        cfg.save()
        r = self.client_for(self.admin).post("/api/access/live-detect/", {"plate_image_base64": "eA=="}, format="json")
        self.assertFalse(r.data["can_auto_grant"])

    def test_drivers_cannot_use_camera_endpoint(self):
        r = self.client_for(self.owner).post("/api/access/live-detect/", {"plate_image_base64": "eA=="}, format="json")
        self.assertEqual(r.status_code, 403)


class PickupTokenTests(Base):
    def test_driver_cannot_mint_token_for_foreign_car(self):
        r = self.client_for(self.thief).post("/api/passkeys/pickup-tokens/", {"vehicle_id": self.car.id}, format="json")
        self.assertEqual(r.status_code, 403)

    @mock.patch("passkeys.views._verify_authentication_payload", return_value=(True, None, None))
    def test_token_redeems_once(self, _):
        self.park()
        pt = PickupToken.issue(self.car, "EXIT")
        c = APIClient()
        r1 = c.post(f"/api/passkeys/pickup-tokens/{pt.token}/authorize/", {"username": "owner", "credential": {}}, format="json")
        self.assertEqual(r1.status_code, 200, r1.data)
        r2 = c.post(f"/api/passkeys/pickup-tokens/{pt.token}/authorize/", {"username": "owner", "credential": {}}, format="json")
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(ParkingSession.objects.get(vehicle=self.car).status, "EXITED")


class AdminEndpointTests(Base):
    def test_stats(self):
        self.park()
        r = self.client_for(self.admin).get("/api/access/stats/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["last_7_days"]), 7)
        self.assertEqual(r.data["active_sessions"], 1)

    def test_policy_validation(self):
        c = self.client_for(self.admin)
        r = c.patch("/api/parking/policy/", {"risk_low_max": 90, "risk_medium_max": 50}, format="json")
        self.assertEqual(r.status_code, 400)
        r = c.patch("/api/parking/policy/", {"capacity": 120, "hourly_rate": "50.00"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(PolicyConfig.current().capacity, 120)  # cache invalidated

    def test_incident_only_on_real_biometric_mismatch(self):
        AccessLog.objects.create(event_type="ENTRY", plate_detected="AAP1478", vehicle=self.car,
                                 status="DENIED", plate_match=True, biometric_match=False)
        self.assertEqual(Incident.objects.count(), 0)


class SignedFileTests(Base):
    def test_signed_url_round_trip_and_tamper(self):
        from django.core.files.storage import default_storage

        name = default_storage.save("docs/test/x.txt", ContentFile(b"hello"))
        c = APIClient()
        self.assertEqual(c.get(f"/api/files/{sign_path(name)}/").status_code, 200)
        self.assertEqual(c.get(f"/api/files/{sign_path(name)}x/").status_code, 404)
        with override_settings(SIGNED_FILE_URL_TTL_SECONDS=-1):
            self.assertEqual(c.get(f"/api/files/{sign_path(name)}/").status_code, 404)
        default_storage.delete(name)
