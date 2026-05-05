# Sentinel — Biometric Parking System

> Smart Parking Surveillance & Recognition System combining **License Plate Recognition (OCR)** and **Biometric (Face) Authentication** to automate vehicle access control.



---

## Table of contents

1. [What's inside](#whats-inside)
2. [Tech stack](#tech-stack)
3. [Prerequisites](#prerequisites)
4. [Setup — step by step (first-time Python user friendly)](#setup--step-by-step-first-time-python-user-friendly)
5. [Daily development workflow](#daily-development-workflow)
6. [Project walkthrough / how to demo](#project-walkthrough--how-to-demo)
7. [API reference](#api-reference)
8. [Folder structure](#folder-structure)
9. [Troubleshooting](#troubleshooting)

---

## What's inside

```
biometric-parking-system/
├── backend/        ← Django + Django REST Framework API server
└── frontend/       ← Next.js 14 (App Router) admin dashboard
```

### Features (mapped to the FYP SRS)

| FR-ID  | Feature                                | Where to see it                                     |
|--------|----------------------------------------|------------------------------------------------------|
| FR-01  | User & vehicle registration            | `/dashboard/users/new`, `/dashboard/vehicles/new`    |
| FR-02  | Image capture                          | `/dashboard/entry` (file upload + webcam)            |
| FR-03  | License plate detection                | OpenCV contour-based detection in `recognition/plate_ocr.py` |
| FR-04  | License plate recognition (OCR)        | Tesseract OCR, same file                             |
| FR-05  | Vehicle verification                   | `POST /api/access/verify-entry/`                     |
| FR-06  | Biometric authentication               | `recognition/face_engine.py`, 128-d face encodings   |
| FR-07  | Barrier gate control                   | Animated SVG gate on the result screen               |
| FR-08  | Access notification                    | GRANTED / DENIED card with reason                    |
| FR-09  | Logging & monitoring                   | `/dashboard/logs` + `/dashboard/` overview           |

---

## Tech stack

**Backend** Django 5 · Django REST Framework · SimpleJWT · OpenCV · Tesseract · `face_recognition` (dlib) · SQLite

**Frontend** Next.js 14 (App Router) · TypeScript · Tailwind CSS · `react-webcam` · `lucide-react`

**Aesthetic** Dark UI with electric-amber accents — Bricolage Grotesque (display), Inter (body), JetBrains Mono (data). Surveillance/security feel.

---

## Prerequisites

You need to install these system-level tools **once** on your machine. None of them are Python packages.

### 1. Python 3.10+ and Node.js 18+

| Platform | Python                                                              | Node.js                                  |
|----------|---------------------------------------------------------------------|------------------------------------------|
| Windows  | <https://www.python.org/downloads/> — tick **"Add to PATH"**        | <https://nodejs.org/> (LTS)              |
| macOS    | `brew install python@3.11`                                          | `brew install node`                      |
| Linux    | `sudo apt install python3.11 python3.11-venv python3-pip`           | `curl -fsSL https://deb.nodesource.com/setup_20.x \| sudo -E bash - && sudo apt install -y nodejs` |

Verify in a terminal:
```bash
python --version    # should be 3.10 or higher
node --version      # should be v18 or higher
```

> On **Windows** the command is sometimes `python` and sometimes `py` — use whichever works. On **macOS/Linux**, prefer `python3`.

### 2. Tesseract OCR (the binary, not the Python wrapper)

This reads text from license plate images. The `pytesseract` Python package alone is not enough — you must install the actual program.

| Platform | Install                                                                                  |
|----------|-------------------------------------------------------------------------------------------|
| Windows  | Download from <https://github.com/UB-Mannheim/tesseract/wiki> · run installer · default path is `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| macOS    | `brew install tesseract`                                                                  |
| Linux    | `sudo apt install tesseract-ocr`                                                          |

Verify:
```bash
tesseract --version
```

> **Windows users:** if `tesseract` is not on PATH, set the full path in `backend/.env` as `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`

### 3. CMake (only needed to build dlib/face_recognition from source)

`face_recognition` depends on `dlib`, which is a C++ library. On modern Python pre-built wheels are usually available — but if pip needs to compile it, you'll need CMake and a C++ compiler.

| Platform | Install                                                                  |
|----------|---------------------------------------------------------------------------|
| Windows  | Install **Visual Studio Build Tools 2022** (C++ workload). Plus `pip install cmake` |
| macOS    | `brew install cmake` (Xcode command-line tools usually already present)   |
| Linux    | `sudo apt install build-essential cmake`                                  |

If you're stuck installing dlib on Windows, see [Troubleshooting](#troubleshooting).

---

## Setup — step by step (first-time Python user friendly)

Open a terminal in the project root (the folder containing this README).

### Step 1 — Backend setup

```bash
cd backend
```

#### 1a. Create a virtual environment

A virtual environment is an isolated folder for this project's Python packages — it keeps things tidy.

```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Windows (cmd.exe)
python -m venv venv
venv\Scripts\activate.bat

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

After activation your prompt will start with `(venv)`. **Every time you open a new terminal window**, you must run the activation command again.

> If PowerShell complains about scripts being disabled, run once:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

#### 1b. Install Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will take 5–10 minutes the first time, mostly because `dlib` (the face-recognition engine) compiles against your CPU.

#### 1c. Create the `.env` file

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `backend/.env` in any editor. The defaults are fine. **Windows users:** if Tesseract isn't on PATH, set `TESSERACT_CMD` to the full executable path.

#### 1d. Apply database migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

This creates `db.sqlite3` with all the tables.

#### 1e. Create the default admin user

```bash
python manage.py seed_admin
```

This prints:
```
Created admin user → username='admin'  password='admin12345'
```

#### 1f. Start the backend server

```bash
python manage.py runserver
```

The API is now running at <http://localhost:8000>. Leave this terminal open.

---

### Step 2 — Frontend setup

Open a **second** terminal (the backend keeps running in the first).

```bash
cd frontend
```

#### 2a. Install Node dependencies

```bash
npm install
```

This takes 1–2 minutes the first time.

#### 2b. Create the `.env.local` file

```bash
# Windows
copy .env.local.example .env.local

# macOS / Linux
cp .env.local.example .env.local
```

The defaults point to the local backend — no changes needed.

#### 2c. Start the frontend

```bash
npm run dev
```

Your dashboard is at <http://localhost:3000>.

---

### Step 3 — Log in

Open <http://localhost:3000> in your browser.

| Username | Password    |
|----------|-------------|
| admin    | admin12345  |

You should land on the **Overview** dashboard.

---

## Daily development workflow

After the one-time setup, here's what you run every time you sit down to work:

**Terminal 1 — backend**
```bash
cd backend
# Windows
.\venv\Scripts\Activate.ps1
# macOS/Linux
source venv/bin/activate

python manage.py runserver
```

**Terminal 2 — frontend**
```bash
cd frontend
npm run dev
```

That's it.

---

## Project walkthrough / how to demo

Use this sequence to show off the system end-to-end (e.g. for your supervisor):

1. **Log in** with `admin / admin12345`.
2. Go to **Users → Add user**. Create a new driver (e.g. *Ali Khan*, role=Driver). The form will redirect you to **biometric enrollment** automatically.
3. **Enroll the face** — sit in front of your webcam, hit *Capture face*, then *Save biometric*. You'll see a green "Enrolled" pill.
4. Go to **Vehicles → Register vehicle**. Pick *Ali Khan* as the owner, enter a plate number (e.g. `LEA-1234`), pick a vehicle type, save.
5. Go to **Live Entry** — this is the demo page.
   - **Step 1:** Upload a photo of a vehicle (any car image works for the demo; for the OCR to find a real match, the plate in the image must say `LEA-1234`).
   - **Step 2:** Capture your face on the webcam.
   - **Step 3:** Hit *Verify & Open Gate*. Watch the animated barrier gate either swing open (GRANTED) or stay closed (DENIED) with a full breakdown of why.
6. Go to **Access Logs** to see the entry recorded with snapshot, plate match status, and biometric distance.
7. Refresh the **Overview** to see updated stats and a 7-day chart.

> 💡 **Demo tip for plate OCR:** Find a sample license-plate image online, then put a printout in front of the camera (or upload a photo of one). The plate text in the image must match a registered plate exactly for a successful match.

---

## API reference

All endpoints (except `/auth/login/` and `/auth/refresh/`) require `Authorization: Bearer <access_token>`.

### Authentication

| Method | Endpoint                  | Description                              |
|--------|---------------------------|------------------------------------------|
| POST   | `/api/auth/login/`        | Returns `{access, refresh, user}`        |
| POST   | `/api/auth/refresh/`      | Refresh an access token                  |
| GET    | `/api/auth/me/`           | Current user                             |
| POST   | `/api/auth/change-password/` | `{old_password, new_password}`        |

### Users (admin only)

| Method | Endpoint                | Description                  |
|--------|-------------------------|------------------------------|
| GET    | `/api/auth/users/`      | List, supports `?search=&role=` |
| POST   | `/api/auth/users/`      | Create user                  |
| GET    | `/api/auth/users/<id>/` | Detail                       |
| PATCH  | `/api/auth/users/<id>/` | Update                       |
| DELETE | `/api/auth/users/<id>/` | Delete                       |

### Vehicles (admin only)

| Method | Endpoint                              | Description                        |
|--------|---------------------------------------|------------------------------------|
| GET    | `/api/vehicles/`                      | List, supports `?search=&owner=`   |
| POST   | `/api/vehicles/`                      | Create vehicle                     |
| GET    | `/api/vehicles/<id>/`                 | Detail                             |
| PATCH  | `/api/vehicles/<id>/`                 | Update                             |
| DELETE | `/api/vehicles/<id>/`                 | Delete                             |
| GET    | `/api/vehicles/lookup/<plate>/`       | Find vehicle by plate              |
| POST   | `/api/vehicles/detect-plate/`         | Run OCR on an image (no decision)  |

### Biometrics

| Method | Endpoint                              | Description                                  |
|--------|---------------------------------------|----------------------------------------------|
| POST   | `/api/biometrics/enroll/`             | `{user_id, image_base64}` → store encoding   |
| POST   | `/api/biometrics/verify/`             | `{user_id, image_base64}` → verify a face    |
| GET    | `/api/biometrics/profile/<user_id>/`  | Profile metadata                             |

### Access (the main one)

| Method | Endpoint                       | Description                                          |
|--------|--------------------------------|------------------------------------------------------|
| POST   | `/api/access/verify-entry/`    | End-to-end gate decision (plate + face → GRANTED/DENIED) |
| GET    | `/api/access/logs/`            | List logs, supports `?status=&plate=&from=&to=`      |
| GET    | `/api/access/stats/`           | Dashboard stats                                      |

#### Example: end-to-end verification

```http
POST /api/access/verify-entry/
Content-Type: application/json
Authorization: Bearer <token>

{
  "plate_image_base64": "data:image/jpeg;base64,/9j/4AAQS…",
  "face_image_base64":  "data:image/jpeg;base64,/9j/4AAQS…"
}
```

Response:
```json
{
  "decision": "GRANTED",
  "reason": "Vehicle registered and biometric verified.",
  "plate": {
    "number": "LEA-1234",
    "registered": true,
    "ocr_confidence": "high",
    "raw_text": "LEA-1234",
    "found_plate": true
  },
  "biometric": {
    "matched": true,
    "distance": 0.3812,
    "found_face": true
  },
  "log_id": 42,
  "timestamp": "2026-05-05T12:34:56.789012+00:00"
}
```

---

## Folder structure

```
biometric-parking-system/
│
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── core/                       ← Django project settings
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py / asgi.py
│   ├── accounts/                   ← Custom User + JWT auth
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── permissions.py          ← IsAdminRole
│   │   ├── urls.py / admin.py
│   │   └── management/commands/seed_admin.py
│   ├── vehicles/                   ← Vehicle CRUD + OCR endpoint
│   ├── biometrics/                 ← Face enrollment + verification
│   ├── access/                     ← AccessLog + verify-entry + stats
│   └── recognition/                ← OCR engine + face engine
│       ├── plate_ocr.py            ← OpenCV plate detection + Tesseract
│       └── face_engine.py          ← face_recognition wrapper
│
└── frontend/
    ├── package.json
    ├── tailwind.config.ts
    ├── next.config.js
    ├── tsconfig.json
    └── src/
        ├── app/
        │   ├── layout.tsx          ← Root layout, fonts, AuthProvider
        │   ├── page.tsx            ← Redirects to /login or /dashboard
        │   ├── login/page.tsx      ← Split-screen login
        │   └── dashboard/
        │       ├── layout.tsx      ← Sidebar wrapper, route protection
        │       ├── page.tsx        ← Overview / stats
        │       ├── entry/page.tsx  ← ⭐ Live Entry simulation
        │       ├── vehicles/
        │       │   ├── page.tsx
        │       │   └── new/page.tsx
        │       ├── users/
        │       │   ├── page.tsx
        │       │   ├── new/page.tsx
        │       │   └── [id]/biometric/page.tsx
        │       └── logs/page.tsx
        ├── components/             ← Sidebar, Topbar, StatCard, WebcamCapture, …
        └── lib/                    ← api.ts, auth.tsx, utils.ts
```

---

## Troubleshooting

### `dlib` / `face_recognition` won't install on Windows

This is the #1 pain point.

**Option A — use a pre-built wheel (easiest):**
```bash
pip install cmake
pip install dlib-bin              # pre-built binary, often works
pip install face-recognition
```

**Option B — install Visual Studio C++ build tools:**
1. Install **Visual Studio Build Tools 2022** with the *Desktop development with C++* workload from <https://visualstudio.microsoft.com/downloads/>.
2. Restart your terminal.
3. Re-run `pip install -r requirements.txt`.

**Option C — use conda instead of pip (works on every OS):**
```bash
conda create -n parking python=3.11
conda activate parking
conda install -c conda-forge dlib
pip install -r requirements.txt
```

### Tesseract not found

```
TesseractNotFoundError: tesseract is not installed or it's not in your PATH
```

Set the full path in `backend/.env`:
```
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```
Then restart the Django server.

### CORS errors in the browser console

By default the backend allows requests from `http://localhost:3000` and `http://127.0.0.1:3000`. If you run the frontend on a different port, edit `CORS_ALLOWED_ORIGINS` in `backend/.env`.

### Webcam doesn't show up

* Browsers only allow camera access on `localhost` or `https://`. `http://192.168.x.x:3000` will be blocked.
* On first use, the browser will prompt for permission — make sure to allow it.
* If the webcam is busy in another app (Zoom, Skype), close that app first.

### "No face detected"

* Make sure your face is well-lit and roughly fills the frame.
* Remove glasses if reflections are heavy.
* Try moving slightly closer to the camera.

### "License plate could not be read"

OCR is not magic — it depends heavily on image quality. Tips:
* Use a clear, in-focus, well-lit photo.
* The plate should be roughly horizontal and not tilted.
* For demos, you can bypass OCR by sending `plate_number` directly to `/api/access/verify-entry/` instead of `plate_image_base64`.

### `npm install` fails

```bash
npm cache clean --force
rm -rf node_modules package-lock.json   # or `del /s` on Windows
npm install
```

### Server won't start: `Error: That port is already in use`

Backend:  `python manage.py runserver 8001`
Frontend: `npm run dev -- -p 3001`

(Don't forget to update `NEXT_PUBLIC_API_URL` in `frontend/.env.local` if you change the backend port, and `CORS_ALLOWED_ORIGINS` in `backend/.env` if you change the frontend port.)

---


