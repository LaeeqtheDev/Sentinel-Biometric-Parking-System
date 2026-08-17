<h1 align="center">Sentinel · Biometric Parking System</h1>

<p align="center">
  Physical access control for a parking facility — license-plate OCR for identification,
  device-bound passkeys for authorisation, and an audit trail for everything the cameras got wrong.
</p>

<p align="center">
  <a href="https://sentinel-biometric-parking-system.vercel.app"><img src="https://img.shields.io/badge/Live_App-000000?style=for-the-badge&logo=vercel&logoColor=white" alt="Live app"></a>
  <img src="https://img.shields.io/badge/Django_REST-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django REST">
  <img src="https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white" alt="Next.js">
  <img src="https://img.shields.io/badge/Oracle_Cloud-F80000?style=for-the-badge&logo=oracle&logoColor=white" alt="Oracle Cloud">
</p>

<p align="center"><em>Final-Year Project — The University of Lahore</em></p>

---

## Overview

A camera watches the entrance and reads plates continuously. When a registered vehicle is recognised, a parking session opens. When the driver returns, they authorise their own exit from their phone — the OS prompts for FaceID or fingerprint, the gate opens, the session closes.

What separates this from a CRUD app is that **the software controls a physical barrier and tracks state that exists in the real world.** A web app that loses a row shows a stale list. A gate system that loses a session either traps a car inside or lets an unauthorised one out. Every design decision below follows from the fact that the database and the parking lot must not disagree, and that the camera, the network and the biometric hardware will each fail at some point.

---

## Security Model

This is the part worth reading. A system described as "biometric" usually means it stores biometrics. This one mostly doesn't, deliberately.

### Passkeys keep biometrics on the device

Authorisation uses **WebAuthn passkeys**. The driver's fingerprint or face is verified by their phone's secure enclave and never transmitted anywhere. The server stores a public key and a credential ID — nothing else. The consequences:

- **A database breach yields no biometric data.** There is nothing to steal but public keys, which are useless without the private key that cannot leave the device.
- **Credentials are revocable.** A compromised passkey is deleted and re-enrolled. This is the property that matters most, because *a face is not revocable* — a person who loses control of their face encoding cannot be issued a new face.
- **Phishing resistance is structural.** WebAuthn binds credentials to an origin, so a credential registered for this system cannot be replayed against another.

### The face-recognition fallback is the risky path, and it's labelled as such

`face_recognition` encodings are stored server-side as a fallback for drivers whose devices can't do WebAuthn. This path stores biometric data — special-category personal data under GDPR — and it is the weakest part of the system by design rather than by oversight. It exists because a gate with no fallback strands people; it is scoped as narrowly as possible, and a production deployment serving EU users would need a lawful basis, explicit consent, retention limits and encryption at rest before it could be enabled at all.

Stating this plainly is the point. "We use biometrics" and "we store biometrics" are different claims with very different liability, and a system should be honest about which one it is on each path.

### The pickup QR is not a credential

Kiosk-QR exit issues a short-lived token (`PICKUP_TOKEN_TTL_SECONDS`, default 300) that lands the driver on a public page. The token alone opens nothing — redemption still requires a passkey assertion from the driver's own device. So a photographed or forwarded QR code is worthless without the enrolled phone, which makes the QR a *pointer to a session*, not a bearer credential. Short TTL limits the window in which even that pointer is meaningful.

### Overrides are audited, not hidden

Every gate action, including admin overrides, writes to `AccessLog` with actor and timestamp. In physical access control the important question after an incident is not "what does the state say" but "who authorised this, when, and through which path." An override capability without an audit trail is an unaccountable master key.

---

## Architecture

```
              ┌─────────────┐
              │   Camera    │   continuous OCR every 2.5s, 30s per-plate debounce
              └──────┬──────┘
                     ▼
┌──────────────────────────────────────────────────────────────┐
│   Django REST API  ·  Oracle Cloud Infrastructure            │
│   /api/auth/         JWT login + user CRUD                   │
│   /api/vehicles/     M2M user↔vehicle (OWNER/DRIVER/BOTH)    │
│   /api/biometrics/   face encodings (fallback path only)      │
│   /api/passkeys/     WebAuthn register / auth + pickup tokens │
│   /api/parking/      Session lifecycle, active + historical   │
│   /api/access/       verify-entry, verify-exit, live-detect   │
└──────────────────────────────────────────────────────────────┘
                     ▲
        ┌────────────┴────────────┐
        │  Next.js  ·  Vercel     │
        ├─────────────────────────┤
   /dashboard/* (admin)      /driver/* (mobile-first)
   Live camera feed          My vehicles + sessions
   Parking sessions          Passkey enrolment
   Manual gate control       One-tap pickup
   Vehicle assignments       QR scan landing
   Audit log
```

**Split deployment.** The Django API runs on Oracle Cloud Infrastructure — the OCR and face-encoding work needs a persistent host with native dependencies (Tesseract, dlib), which rules out serverless. The Next.js frontend deploys to Vercel. Two hosts means CORS and WebAuthn origin configuration are real concerns rather than defaults: `WEBAUTHN_RP_ID` and `WEBAUTHN_ORIGINS` must match the browser's actual origin exactly, over HTTPS, or assertions fail with an error that tells you nothing.

**Relationships model reality, not convenience.** `UserVehicle` is a junction table with an explicit `OWNER | DRIVER | BOTH` relationship, because one car has several authorised drivers and one driver has several cars. A foreign key from vehicle to user would have been simpler and wrong.

**Sessions are a state machine.** A plate with an open session cannot open another — duplicate entries are rejected rather than deduplicated later. This is idempotency applied to a physical event, and it's what keeps the count of cars in the database equal to the count of cars in the lot.

**Failure handling is a feature.** OCR returns confidence, and the live feed acts only on high and medium reads. In a gate system the two error directions are not symmetrical: a false reject is a driver waiting thirty seconds for a manual override, while a false accept is an unauthorised vehicle inside a facility. The thresholds are set to prefer the first, and the manual override path exists precisely so that preferring it is affordable.

---

## Key Flows

**Registration** — Admin creates a `Vehicle` and links users via `UserVehicle`, each link carrying its relationship type.

**Entry** — Camera OCRs plates continuously. A high-confidence read that hasn't been seen in 30 seconds triggers the gate and opens a `ParkingSession`. A biometric or passkey check can be required at the gate.

**Exit, driver-app** — Driver opens `/driver/pickup`, taps their parked car, the OS prompts for FaceID or fingerprint, WebAuthn assertion verifies server-side, gate opens, session closes.

**Exit, kiosk-QR** — Admin generates a pickup QR for an active session. Driver scans it, lands on `/driver/scan/<token>`, identifies themselves, biometric prompt fires on their own device, gate opens.

---

## Tech Stack

| Layer | Choice | Reasoning |
|---|---|---|
| API | Django REST Framework | Mature auth, admin and ORM; Python is where the CV and face libraries live |
| Frontend | Next.js + TypeScript | Two distinct shells — desktop admin and mobile-first driver — from one codebase |
| Auth | JWT + WebAuthn passkeys | Session auth for the app; device-bound assertions for gate authorisation |
| Plate OCR | Tesseract (`pytesseract`) | Runs locally with no per-request cost or third-party image upload |
| Face fallback | `face_recognition` / dlib | Only path that stores biometric data; scoped and documented as such |
| API host | Oracle Cloud Infrastructure | Persistent host for native OCR/dlib dependencies; serverless can't carry them |
| Frontend host | Vercel | Preview deployments per branch |

---

## Deployment Notes

The development defaults in this README are **not production settings**. Before exposing an instance:

- `DEBUG=False`, and `ALLOWED_HOSTS` set to explicit hostnames — a wildcard invites host-header attacks
- Replace the seeded `admin` account and its default password immediately; never seed default credentials on a reachable host
- `SECRET_KEY` from the environment, never a committed default
- `WEBAUTHN_RP_ID` and `WEBAUTHN_ORIGINS` set to the production HTTPS domain — WebAuthn and `getUserMedia` both require a secure context, so neither works over plain HTTP outside `localhost`
- `CORS_ALLOWED_ORIGINS` limited to the deployed frontend origin
- Postgres rather than SQLite; the dev flow drops `db.sqlite3`, which is not a migration strategy

---

<details>
<summary><strong>Local Setup (Windows)</strong></summary>

Tested on Windows 11, Python 3.11.9, Node 20.

**Prerequisites**

- Python 3.11.9 — 3.13/3.14 will not work, as `face-recognition`/dlib have no wheels for them
- Node.js 20+
- Tesseract OCR — note the install path, usually `C:\Program Files\Tesseract-OCR`

**Backend**

```powershell
cd backend
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1        # (venv) must appear in the prompt
python -m pip install --upgrade pip
pip install cmake
pip install -r requirements.txt
pip install face-recognition==1.3.0 --no-deps
```

Create `backend/.env`:

```bash
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000

TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
FACE_MATCH_TOLERANCE=0.6

WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=Sentinel Parking
WEBAUTHN_ORIGINS=http://localhost:3000

FRONTEND_BASE_URL=http://localhost:3000
PICKUP_TOKEN_TTL_SECONDS=300
```

```powershell
python manage.py makemigrations accounts vehicles biometrics access parking passkeys
python manage.py migrate
python manage.py seed_admin
python manage.py runserver
```

**Frontend**

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

The seeded admin account exists for first login only — change the password before the instance is reachable from anywhere but your machine.

</details>

<details>
<summary><strong>Troubleshooting</strong></summary>

**dlib build fails / Visual Studio required** — you're building from source; use the wheel:

```bash
pip install dlib-bin
pip install face-recognition==1.3.0 --no-deps
```

**`(venv)` doesn't appear** — activation was blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\venv\Scripts\Activate.ps1
```

**WebAuthn returns "operation not allowed"** — requires HTTPS or `localhost`. If `WEBAUTHN_RP_ID=localhost`, don't browse via `127.0.0.1`; the origin must match `WEBAUTHN_ORIGINS` exactly.

**Camera doesn't open** — `getUserMedia` needs a secure context. `localhost` qualifies; anything else needs HTTPS.

**`pytesseract.TesseractNotFoundError`** — set `TESSERACT_CMD` to the full path of `tesseract.exe`.

</details>

<details>
<summary><strong>API Reference</strong></summary>

**Auth** — `POST /api/auth/login/` · `POST /api/auth/refresh/` · `GET /api/auth/me/` · `GET /api/auth/users/`

**Vehicles** — `GET|POST /api/vehicles/` · `GET /api/vehicles/my/` · `GET|POST /api/vehicles/<id>/assignments/` · `DELETE /api/vehicles/<id>/assignments/<aid>/` · `GET /api/vehicles/lookup/<plate>/` · `POST /api/vehicles/detect-plate/`

**Access** — `POST /api/access/verify-entry/` · `POST /api/access/verify-exit/` · `POST /api/access/live-detect/` · `POST /api/access/manual-override/` · `GET /api/access/logs/` · `GET /api/access/stats/`

**Parking** — `GET /api/parking/sessions/` (`?status=PARKED|EXITED`) · `GET /api/parking/sessions/active/` · `GET /api/parking/my/` · `GET /api/parking/active-for/<plate>/`

**Passkeys** — `POST /api/passkeys/register/options/` · `POST /api/passkeys/register/verify/` · `POST /api/passkeys/auth/options/` · `POST /api/passkeys/auth/verify/` · `GET /api/passkeys/my/` · `DELETE /api/passkeys/credentials/<id>/` · `POST /api/passkeys/pickup-tokens/` · `GET /api/passkeys/pickup-tokens/<token>/` · `POST /api/passkeys/pickup-tokens/<token>/authorize/`

**Biometrics (fallback)** — `GET /api/biometrics/` · `POST /api/biometrics/enroll/` · `POST /api/biometrics/verify/`

</details>

<details>
<summary><strong>Project Layout</strong></summary>

```
backend/
├── core/           Django config (settings, urls, wsgi)
├── accounts/       Custom User (ADMIN | DRIVER) + JWT
├── vehicles/       Vehicle + UserVehicle (M2M) + plate normalisation
├── biometrics/     Face encodings (fallback auth)
├── passkeys/       WebAuthn credentials + pickup tokens
├── parking/        ParkingSession entry/exit lifecycle
├── access/         AccessLog + verify-entry / verify-exit / live-detect
├── recognition/    plate_ocr.py (Tesseract) + face_engine.py
└── manage.py

frontend/src/
├── app/
│   ├── dashboard/  Admin shell — live camera, sessions, vehicles, users, logs
│   └── driver/     Mobile-first — pickup, passkey enrolment, scan/[token]
├── components/     Sidebar, Topbar, Webcam, primitives
└── lib/            api.ts (JWT auto-refresh), auth.tsx, webauthn.ts, utils.ts
```

</details>

---

## Trade-offs

- **Plate OCR is the identification layer, and OCR is fallible.** Weather, angle, plate design and motion all degrade reads. Tesseract on a general model is well short of a purpose-trained ALPR pipeline; the confidence thresholds and manual override exist because of that, not in spite of it.
- **The face fallback stores biometric data.** Documented above. It is the one path in the system that would create regulatory obligations in a real deployment, and the reason it exists is accessibility rather than security.
- **Native dependencies constrain the host.** dlib and Tesseract pin the backend to Python 3.11 and a persistent VM. That's a real operational cost and the reason this can't move to a serverless platform without replacing the recognition stack.
- **No automated tests.** For a system whose failure modes are physical, this is the gap I'd close first — particularly session-lifecycle invariants and the WebAuthn verification path, where a regression grants access rather than denying it.
- **Single camera, single gate.** The model assumes one entrance. Multiple gates would need per-gate session routing and a way to reconcile a vehicle entering at one and exiting at another.
- **No offline behaviour.** If the API is unreachable, the gate has no independent fallback. A production installation would need a local decision path and reconciliation on reconnect.

---

## Roadmap

- [ ] Test coverage on session lifecycle invariants and WebAuthn verification
- [ ] Purpose-trained ALPR model in place of general-purpose OCR
- [ ] Encryption at rest and retention policy for the face-encoding fallback
- [ ] Multi-gate support with per-gate session routing
- [ ] Offline gate decisions with reconciliation on reconnect
- [ ] Structured metrics on OCR confidence distribution and override frequency

---

## Author

**Syed Laeeq Ahmed** — Full-Stack Lead Engineer @ North Foundry

[Portfolio](https://laeeqthedevportfolio.vercel.app) · [LinkedIn](https://www.linkedin.com/in/syed-laeeq-ahmed/) · [GitHub](https://github.com/LaeeqtheDev) · laeeqthedev@gmail.com

## License

All rights reserved. Source is public to read; not licensed for reuse or redeployment.
