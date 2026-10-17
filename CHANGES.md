# Sentinel: security, system design and scalability overhaul

This release fixes the design flaws found in an audit of the codebase, makes
the system horizontally scalable, and adds a public landing page.
Backend regression tests: `cd backend && DEBUG=True python manage.py test core` (24 tests).

## 1. Critical security fixes

| # | Flaw | Impact | Fix |
|---|------|--------|-----|
| 1 | `verify-exit` / `verify-entry` trusted a client-supplied `webauthn_user_id` | **Any logged-in driver could open the exit for any car** by posting the owner's user id. No passkey was involved in that request. | Passkey verification now returns a signed, single-use, 60-second `passkey_ticket` bound to the verified user (`passkeys/tickets.py`). Gate endpoints accept only the ticket. `webauthn_user_id` is rejected. |
| 2 | Drivers could call the gate endpoints for any vehicle | Same as above, plus probing other people's cars | Drivers can only act on vehicles they are an **approved** user of, and only as themselves. |
| 3 | `admin_override` was honoured for any caller, and `"false"` parsed as true | Drivers could request overrides; a string flag silently granted | Override is admin-only, parsed as a real boolean, and always audited with the admin's name. |
| 4 | Claiming an already-registered plate linked the claimant immediately and flipped the owner's car to UNDER_REVIEW | Attach yourself to a stranger's car, then unlock it; or knock any car out of service by typing its plate | Claims on existing plates create an **unapproved** link that grants nothing until an admin approves it. The owner's car is untouched. New "Requests to use an existing vehicle" queue on the approvals page (`vehicles/claims.py`). |
| 5 | Any user could mint QR pickup tokens for any vehicle | Kiosk flow abuse | Admins, or approved users of that vehicle, only. Redemption locks the token row so it can be used exactly once. |
| 6 | Passkeys did not require user verification (`require_user_verification=False`) | "Biometric" exit worked with device possession alone | User verification (Face ID / fingerprint) is required at registration and sign-in. |
| 7 | WebAuthn challenge = "latest unconsumed for this user" | Concurrent devices broke each other; challenge could be raced | Challenge matched by value from `clientDataJSON` and consumed with a conditional UPDATE. |
| 8 | `/biometrics/verify/` accepted any `user_id` from any user | Face-matching oracle against other users | Drivers can only verify against their own enrolment. |
| 9 | All media (CNIC scans, licences, face photos, gate snapshots) under public `/media/` (and only served when DEBUG) | Identity documents exposed by guessable URL; broken in production | Private storage. Files are served via short-lived signed links `/api/files/<token>/` (`core/files.py`). Optional S3-compatible bucket (Oracle Object Storage / S3 / R2). |
| 10 | Insecure defaults: `DEBUG=True`, `ALLOWED_HOSTS=*`, committed default `SECRET_KEY`; `seed_admin` reset the admin password to `admin12345` on every run and printed it | Trivial takeover of a misconfigured deploy | Production refuses to boot without a secret key, explicit hosts, Postgres and Redis. HSTS, secure cookies, SSL redirect. `seed_admin` needs an explicit password in production and never resets or prints it. |
| 11 | No rate limits | Password and passkey brute force, user enumeration, camera spam | Per-scope throttles (login, register, passkey, gate, camera) stored in Redis. Passkey endpoints no longer reveal which usernames exist. |
| 12 | 12-hour access tokens, no revocation | Stolen token valid for half a day, logout did nothing server-side | 15-minute access tokens, rotating refresh tokens with blacklist, real `/auth/logout/`. |
| 13 | Weak passwords accepted (6 chars, validators skipped) | | Django password validators enforced everywhere (min 8). |
| 14 | Uploads unchecked (25 MB JSON bodies, any file type, pixel bombs) | DoS, stored junk | Document type/size validation by magic bytes; images bounded by pixel count and downscaled before OCR. |

## 2. Correctness and data-integrity fixes

* **Race conditions on the gate.** Five code paths each did "check for an active session, then create one" with no transaction. Two frames processed at once could double-enter (500 from the unique constraint) or double-exit. All paths now go through `parking/services.py` (`admit` / `release`): one transaction, row lock on the vehicle, capacity check under lock.
* **Missing migration** for `User.gate_registered`: walk-up registration would crash on a fresh database. Added.
* **Dashboard 7-day chart was wrong on Postgres** (`.extra(date(timestamp))` returns `date`, compared to `str`, and ignored the time zone). Rewritten with `TruncDate` in local time.
* **Two different autonomous-mode rule sets.** The live camera used a hand-rolled check that read `AUTONOMOUS_MODE` from the environment and ignored the admin Policy page. It now uses the same risk engine and policy as manual verification, plus the OCR-confidence floors that were configurable but never used.
* **Off-hours window** was hard-coded in two places; now part of the policy.
* **Trust score** used read-modify-write (lost updates) and an over-counting daily cap. Now one atomic UPDATE, with a correct per-day cap in Redis, applied after the gate transaction commits.
* **Incidents** fired a "possible impersonation" alert on every denial without a face image. Now only on a real face mismatch, and repeated-failure incidents fire once per burst.
* **Co-drivers could not use face exit** at the admin gate (only the "primary user" was checked). All approved drivers are matched.
* **Policy page accepted anything** (`setattr` on raw JSON). Now validated (ranges, ordering of thresholds, time formats).
* **Owner "add driver" was broken**: the driver app called admin-only endpoints with the wrong field name. New `POST /vehicles/my/<id>/drivers/` for approved owners.
* Removing your last link to a car no longer deletes the car's whole parking/audit history.
* Frontend no longer replays failed POSTs: the API client retried gate actions on 500, which could act twice. Retries are now for GET only. Token refresh is single-flight so parallel 401s don't log the user out.

## 3. Scalability

| Before | After |
|--------|-------|
| OCR (many Tesseract passes) and dlib face encoding ran **inside the web request**. One camera polling every 2.5 s could pin a worker; a few cameras starved logins and dashboards. | `recognition/service.py` sends CV work to **Celery workers** on a `recognition` queue (`RECOGNITION_ASYNC=True`). The API waits with a timeout and returns 503 instead of hanging. Recognition scales by adding workers, independently of the API. |
| Plate lookup loaded **every vehicle into Python** and compared them one by one, on every frame. | Indexed, unique `plate_canonical` column. One index lookup at any fleet size (data migration included). |
| Debounce relied on per-request DB queries; nothing stopped two workers acting on the same frame. | Shared Redis debounce with atomic `cache.add`, so only one worker can act on a plate per window. |
| Policy row fetched with `get_or_create` on every decision. | Cached in Redis, invalidated on save. |
| N+1 queries everywhere (vehicle owners/drivers, `has_biometric` per user, nested serializers). | Prefetch helpers; list endpoints run a constant number of queries. |
| Dashboard stats: 8+ COUNT queries per load. | One aggregate + one chart query, cached for 10 s. |
| Date filters on logs used `timestamp__date` (no index use). | Range filters plus new composite indexes. |
| Media on local disk: can't run more than one API instance. | S3-compatible storage option, so the API is stateless. |
| Expired challenges and tokens accumulated forever. | `purge_expired` command, scheduled every 10 minutes by Celery beat. |
| Camera sent full-resolution stills (1 to 3 MB base64 every 2.5 s). | Frames capped at 1280 px, JPEG 0.8. |
| No health checks, no process config, no container setup. | `/healthz`, `/readyz`, gunicorn config, Dockerfiles, `docker-compose.yml` with Postgres, Redis, API, workers, beat and frontend. |

## 4. New features

* **Public landing page** at `/` (server-rendered, mobile-friendly, SEO metadata, robots.txt). Previously `/` was a spinner that redirected to login.
* **Capacity control**: total spots in the Policy page; entries are refused when full, safely under concurrency. `GET /api/parking/occupancy/`.
* **Peak / off-peak pricing**: hourly and peak rates, grace period, currency. Fee computed per minute when a session closes (`parking/pricing.py`), handles multi-day stays and windows that cross midnight. Shown to drivers in their session history and returned by verify-exit.
* Admin queue for plate claims; Django admin path configurable (`ADMIN_URL`).

## 5. Upgrade notes

1. `pip install -r backend/requirements-prod.txt` (Django 5.0 to 5.2 LTS, adds Celery, Redis, django-storages, psycopg 3).
2. `python manage.py migrate`. The vehicle migration backfills `plate_canonical`. If two existing rows describe the same physical plate (e.g. `AAP-1478` and `AAP1478`), the newer one is tagged `...DUP<id>` and should be merged by an admin.
3. Existing user to vehicle links are kept and marked approved.
4. Fill `backend/.env` from `.env.example`. In production `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL` and `REDIS_URL` are required.
5. Run workers: `celery -A core worker -Q recognition,default` and `celery -A core beat`, or simply `docker compose up -d --build`.
6. Frontend: set `NEXT_PUBLIC_API_URL`. Drivers' apps pick up the new passkey ticket flow automatically.
7. Note: `frontend/middleware.ts` (the "Service suspended" response) was left untouched. With a `src/` folder Next.js loads `src/middleware.ts` (a pass-through), so the root file is most likely inactive. Decide deliberately whether it should stay.
