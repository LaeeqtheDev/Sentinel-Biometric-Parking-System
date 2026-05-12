# Sentinel · Biometric Parking System

A smart parking surveillance & recognition system built as a Final-Year
Project at the University of Lahore. It combines **license-plate OCR**
with **device-based biometric verification (WebAuthn passkeys)** plus a
**face-recognition fallback** to control access to a parking lot, and
tracks every vehicle's stay as a parking session.

> **Group · Fall-2025-09**
> Muhammad Abdul Basit Malik · Zainab Riaz Ahmed · Orooj Fatima
> Advisor · Ma'am Sadaf Ali

---

## Architecture

```
                ┌─────────────┐
                │   Camera    │  (continuous OCR every 2.5s, debounced)
                └──────┬──────┘
                       │
                       ▼
┌───────────────────────────────────────────────────────────┐
│              Django REST API  (port 8000)                 │
│  /api/auth/         JWT login + user CRUD                 │
│  /api/vehicles/     M2M user↔vehicle (OWNER/DRIVER/BOTH)  │
│  /api/biometrics/   face_recognition encodings (fallback) │
│  /api/passkeys/     WebAuthn register / auth + pickup QR  │
│  /api/parking/      Active + historical sessions          │
│  /api/access/       verify-entry, verify-exit, live-detect│
└───────────────────────────────────────────────────────────┘
                       ▲
                       │
        ┌──────────────┴──────────────┐
        │                             │
   /dashboard/* (admin)         /driver/* (mobile-first)
   - Live camera feed           - My vehicles + sessions
   - Parking sessions           - Passkey enrollment
   - Manual gate (entry/exit)   - One-tap pickup
   - Vehicle assignments        - QR scan landing page
```

### Key flows

**1. Vehicle registration**
Admin creates a Vehicle and links it to one or more Users via the
`UserVehicle` junction table — each link has a `relationship` of
`OWNER`, `DRIVER`, or `BOTH`.

**2. Entry**
Camera continuously OCRs license plates. When a plate is recognised
with high confidence and hasn't been seen for 30 seconds (debounce),
the gate is triggered and a `ParkingSession` is created. Optionally a
biometric or passkey check is performed at the gate.

**3. Exit (the cool part)**
The driver picks up their car using one of two flows:

  - **Driver-app flow** — open `/driver/pickup` on phone, tap a parked
    car, the OS prompts for FaceID/fingerprint via WebAuthn, the gate
    opens, the parking session closes.
  - **Kiosk-QR flow** — admin generates a pickup QR for a session.
    Driver scans with phone camera, lands on `/driver/scan/<token>`,
    enters their username, biometric prompt fires, gate opens.

**4. Failure handling**
  - OCR can return low-confidence reads — the live feed only acts on
    `high`/`medium` confidence detections.
  - Manual override endpoint (`/api/access/manual-override/`) lets
    admins force-open the gate when the camera or biometric fails —
    fully audited.
  - Duplicate-entry attempts are rejected (an open session blocks new
    entries for the same plate).

---

## Setup (Windows)

> Tested on Windows 11 with Python 3.11.9 and Node 20.

### Prerequisites

1. **Python 3.11.9** — `https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe`
   (Python 3.13 / 3.14 will NOT work — face-recognition / dlib don't have wheels yet.)
2. **Node.js 20+** — `https://nodejs.org`
3. **Tesseract OCR** — `https://github.com/UB-Mannheim/tesseract/wiki`
   Install it, then note the install path (usually `C:\Program Files\Tesseract-OCR`).

### Backend

```powershell
cd backend
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1     # MUST see (venv) in your prompt
python -m pip install --upgrade pip
pip install cmake
pip install -r requirements.txt
pip install face-recognition==1.3.0 --no-deps
```

Create a `.env` file in the `backend/` folder:

```
SECRET_KEY=change-me-to-something-long-and-random
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,*
CORS_ALLOWED_ORIGINS=http://localhost:3000

TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
FACE_MATCH_TOLERANCE=0.6

# WebAuthn relying-party identity
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=Sentinel Parking
WEBAUTHN_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Pickup-QR config
FRONTEND_BASE_URL=http://localhost:3000
PICKUP_TOKEN_TTL_SECONDS=300
```

Then run migrations and seed the admin:

```powershell
python manage.py makemigrations accounts vehicles biometrics access parking passkeys
python manage.py migrate
python manage.py seed_admin
python manage.py runserver
```

Default admin credentials: `admin / admin12345` (change immediately).

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. Log in as `admin / admin12345`.

---

## Upgrading from v0.1

If you already had v0.1 installed and want v0.2:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install face-recognition==1.3.0 --no-deps

# v0.2 has a new schema (M2M Vehicle ↔ User, ParkingSession,
# WebAuthn).  The simplest path for a dev install is to drop the DB:
del db.sqlite3
python manage.py makemigrations accounts vehicles biometrics access parking passkeys
python manage.py migrate
python manage.py seed_admin
python manage.py runserver
```

```powershell
cd frontend
npm install   # picks up @simplewebauthn/browser + qrcode.react
npm run dev
```

---

## Demo walkthrough

1. **Admin: register a driver** at `/dashboard/users/new`. Mark them as
   role `DRIVER`.
2. **Admin: register a vehicle** at `/dashboard/vehicles/new` and add
   the driver as `OWNER` (or `BOTH`).
3. **Driver logs in** at `/driver/login` on a phone. Enrolls a passkey
   at `/driver/biometric` (FaceID / fingerprint prompt).
4. **Admin opens** `/dashboard/live-camera`, points camera at the car.
   Plate is detected — admin clicks "Trigger ENTRY". A parking session
   is now open.
5. **Driver returns**, opens `/driver/pickup`, taps the car. Phone
   prompts for biometric → backend verifies → session closes →
   "Access granted".
6. **Alternate exit** — admin opens `/dashboard/sessions`, clicks
   "Pickup QR" on the active session. Shows a QR. Driver scans, runs
   biometric on phone, gate opens.

---

## Endpoints

### Auth
- `POST /api/auth/login/` — JWT login
- `POST /api/auth/refresh/` — refresh token
- `GET  /api/auth/me/` — current user
- `GET  /api/auth/users/` — list users (admin)

### Vehicles
- `GET  /api/vehicles/` — list (admin)
- `POST /api/vehicles/` — create with `assignments: [{user, relationship}]`
- `GET  /api/vehicles/my/` — current user's vehicles
- `GET  /api/vehicles/<id>/assignments/` — list user-vehicle links
- `POST /api/vehicles/<id>/assignments/` — add link
- `DELETE /api/vehicles/<id>/assignments/<aid>/` — remove link
- `GET  /api/vehicles/lookup/<plate>/` — find by plate
- `POST /api/vehicles/detect-plate/` — OCR helper

### Access
- `POST /api/access/verify-entry/` — ENTRY decision
- `POST /api/access/verify-exit/` — EXIT decision
- `POST /api/access/live-detect/` — live-camera frame OCR
- `POST /api/access/manual-override/` — admin force-grant
- `GET  /api/access/logs/` — paginated logs
- `GET  /api/access/stats/` — dashboard statistics

### Parking
- `GET  /api/parking/sessions/` — all sessions, `?status=PARKED|EXITED`
- `GET  /api/parking/sessions/active/` — currently parked
- `GET  /api/parking/my/` — current user's sessions
- `GET  /api/parking/active-for/<plate>/` — is this plate parked?

### Passkeys / WebAuthn
- `POST /api/passkeys/register/options/` — get registration challenge
- `POST /api/passkeys/register/verify/` — verify registration
- `POST /api/passkeys/auth/options/` — get auth challenge
- `POST /api/passkeys/auth/verify/` — verify authentication
- `GET  /api/passkeys/my/` — list my passkeys
- `DELETE /api/passkeys/credentials/<id>/` — remove a passkey
- `POST /api/passkeys/pickup-tokens/` — create QR pickup token
- `GET  /api/passkeys/pickup-tokens/<token>/` — get token info (public)
- `POST /api/passkeys/pickup-tokens/<token>/authorize/` — phone redeems

### Biometrics (face_recognition fallback)
- `GET  /api/biometrics/` — list profiles (admin)
- `POST /api/biometrics/enroll/` — upload + encode a face
- `POST /api/biometrics/verify/` — match against a stored encoding

---

## Troubleshooting

**"dlib build failed / Visual Studio required"**
You're trying to build dlib from source. Use the binary wheel:
```
pip install dlib-bin
pip install face-recognition==1.3.0 --no-deps
```

**`(venv)` doesn't appear in your prompt**
Activation script didn't run. On PowerShell:
```
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\venv\Scripts\Activate.ps1
```

**WebAuthn fails with "operation not allowed"**
WebAuthn requires either `https://` or `localhost`. Don't access via
`127.0.0.1` if the RP_ID is `localhost`. Make sure your backend
`WEBAUTHN_ORIGINS` matches the URL the browser uses.

**Camera doesn't work in browser**
WebAuthn + getUserMedia both require a secure context. `localhost` is
secure, anything else needs HTTPS.

**`pytesseract.TesseractNotFoundError`**
Set `TESSERACT_CMD` in `.env` to the full path of `tesseract.exe`.

---

## Project layout

```
backend/
├── core/           Django config (settings, urls, wsgi)
├── accounts/       Custom User (with role: ADMIN | DRIVER) + JWT
├── vehicles/       Vehicle + UserVehicle (M2M) + plate normalisation
├── biometrics/     face_recognition encodings (fallback auth)
├── passkeys/       WebAuthn credentials + pickup tokens
├── parking/        ParkingSession (entry/exit lifecycle)
├── access/         AccessLog + verify-entry, verify-exit, live-detect
├── recognition/    plate_ocr.py (Tesseract) + face_engine.py
└── manage.py

frontend/
└── src/
    ├── app/
    │   ├── login/                 admin login
    │   ├── dashboard/             admin shell
    │   │   ├── page.tsx           overview + stats
    │   │   ├── live-camera/       continuous OCR feed
    │   │   ├── entry/             manual ENTRY/EXIT verification
    │   │   ├── sessions/          parking sessions + QR pickup
    │   │   ├── vehicles/          CRUD + assignments management
    │   │   ├── users/             user CRUD + biometric enrollment
    │   │   └── logs/              audit log
    │   └── driver/                mobile-first driver dashboard
    │       ├── login/
    │       ├── page.tsx           home / my vehicles
    │       ├── biometric/         passkey enrollment
    │       ├── pickup/            tap-to-exit
    │       ├── sessions/          parking history
    │       └── scan/[token]/      kiosk-QR landing page
    ├── components/                Sidebar, Topbar, Webcam, Button, …
    └── lib/
        ├── api.ts                 fetch wrapper + JWT auto-refresh
        ├── auth.tsx               auth context
        ├── webauthn.ts            @simplewebauthn/browser wrapper
        └── utils.ts               types + date / duration helpers
```
