# CampusCare

CampusCare is a campus maintenance and complaint-management application
designed to help students report infrastructure and facility-related
issues, track their progress, and communicate with the staff assigned to
resolve them.

The application provides a student-facing mobile interface built with
**Python and Flet**, supported by a **FastAPI** backend and **Supabase**
services. It includes complaint submission with photos and location
information, complaint tracking, and staff-side workflows for managing
maintenance requests.

> **Project status:** Development is ongoing. 

## Table of Contents

-   [Features](#features)
-   [Technology Stack](#technology-stack)
-   [Application Architecture](#application-architecture)
-   [Repository Structure](#repository-structure)
-   [Getting Started](#getting-started)
    -   [Prerequisites](#prerequisites)
    -   [Clone the Repository](#clone-the-repository)
    -   [Set Up the Frontend](#set-up-the-frontend)
    -   [Configure the Backend](#configure-the-backend)
    -   [Run the Backend](#run-the-backend)
    -   [Run the Frontend](#run-the-frontend)
-   [Configuration](#configuration)
-   [Building the Android APK](#building-the-android-apk)
-   [How It Works](#how-it-works)
-   [Security and Deployment Notes](#security-and-deployment-notes)
-   [Contributing](#contributing)

## Features

### Student features

-   **Authentication:** Sign up and log in using institutional email
    addresses.
-   **Issue reporting:** Submit maintenance complaints with a category,
    description, building, room and optional location details.
-   **Photo attachments:** Attach up to three images to a complaint. The
    frontend uses Pillow to compress selected images before submission.
-   **Location assistance:** Use device GPS coordinates to suggest a
    nearby campus building. Students can still select a building
    manually.
-   **Complaint dashboard:** View complaint summaries and recent issues.
-   **Issue tracking:** View complaint status, priority, timestamps,
    progress information, comments and available resolution actions.
-   **Worker contact:** When a worker is assigned, open the device's
    phone, SMS or WhatsApp application using the worker's contact
    details. Messages can be prefilled for the relevant complaint.
-   **Profile and session:** View profile information and restore an
    authenticated session when reopening the app.

### Staff and administrative workflows

The repository also contains administrative modules and backend routes
intended to support complaint management, worker assignment and related
operations. The completeness of these workflows varies; consult the
current source code before assuming every administrative feature is
fully integrated.

## Technology Stack

  Layer                      Technologies
  -------------------------- -----------------------------------------
  Frontend                   Python, Flet
  Navigation                 Flet Router
  HTTP communication         HTTPX
  Image processing           Pillow
  Device features            Flet Camera, Flet Geolocator
  Backend                    Python, FastAPI, Uvicorn
  Data and authentication    Supabase, Supabase Auth
  File storage               Supabase Storage
  API format                 REST, JSON, multipart form data
  Authentication mechanism   Bearer access tokens and refresh tokens

## Application Architecture

CampusCare follows a layered frontend architecture:

1.  **Screens (`src/screens/`)** display the user interface and handle
    user interactions.
2.  **Services (`src/services/`)** contain feature-specific operations,
    such as authentication and issue management.
3.  **Core (`src/core/`)** provides shared application infrastructure,
    including API communication, session handling and routing.
4.  **Components (`src/components/`)** provide reusable interface
    elements such as issue cards and status indicators.
5.  **Backend (`backend/`)** exposes FastAPI endpoints, validates
    requests and coordinates authentication, issue operations and
    Supabase access.

Typical request flow:

``` text
Flet Screen
    |
    v
Frontend Service
    |
    v
Central API Client (HTTPX)
    |
    | HTTP request + Bearer access token
    v
FastAPI Backend
    |
    v
Supabase Auth / Database / Storage
    |
    v
HTTP response (JSON)
    |
    v
Frontend Service -> Flet Screen
```

The API client centralizes request construction, authentication headers,
response handling and error handling. It also attempts to refresh an
expired access token after an unauthorized response and retries the
original request once.

## Repository Structure

``` text
CampusCare-SL/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── issues.py
│   │   └── admin.py
│   ├── services/
│   ├── schemas/
│   └── ...
├── src/
│   ├── main.py
│   ├── config.py
│   ├── components/
│   │   ├── issue_card.py
│   │   └── status_chip.py
│   ├── core/
│   │   ├── api_client.py
│   │   ├── router.py
│   │   └── session.py
│   ├── screens/
│   │   ├── admin/
│   │   ├── shared/
│   │   └── student/
│   └── services/
│       ├── auth_service.py
│       └── issue_service.py
├── build.sh
├── manifest.json
├── pyproject.toml
└── requirements.txt
```

The tree above is representative; additional modules and migrations may
be present in the repository.

## Getting Started

### Prerequisites

Install the following:

-   Python 3.10 or later
-   pip
-   Git
-   A Supabase project for backend authentication, database and storage
-   Flet-compatible development environment for the target platform

### Clone the Repository

``` bash
git clone https://github.com/ShreeSamal/CampusCare-SL.git
cd CampusCare-SL
```

### Set Up the Frontend

Create and activate a virtual environment:

**macOS / Linux**

``` bash
python -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**

``` powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the dependencies:

``` bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The frontend dependencies include Flet, HTTPX, Pillow, Flet Camera and
Flet Geolocator.

### Configure the Backend

Create a `.env` file in the `backend/` directory. The backend settings
expect the following environment variables:

``` env
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
ALLOWED_EMAIL_DOMAIN=iitb.ac.in
```

Use the values from your own Supabase project. Do not commit `.env`
files or expose the service-role key in the frontend or in a public
repository.

Before running the backend, ensure that the required Supabase tables,
authentication settings, storage bucket and database policies/migrations
have been configured. The issue API currently uses an `issue-photos`
storage bucket by default; check the backend configuration and storage
policies for your deployment.

Install backend dependencies:

``` bash
cd backend
pip install -r requirements.txt
```

### Run the Backend

From the `backend/` directory, start the FastAPI development server:

``` bash
uvicorn main:app --reload
```

The API will normally be available at:

-   API base: `http://127.0.0.1:8000/api`
-   Health check: `http://127.0.0.1:8000/api/health`
-   Interactive API documentation: `http://127.0.0.1:8000/docs`

Keep the backend running while developing against a local API.

### Run the Frontend

Open a second terminal, activate the frontend virtual environment and
run the Flet application from the repository root:

``` bash
flet run
```

If your environment requires an explicit entry point, run the app using
the Flet CLI with `src/main.py` as the application entry point.

For a local backend, update `API_BASE_URL` in `src/config.py` to point
to the backend reachable from the device running the frontend:

``` python
API_BASE_URL = "http://127.0.0.1:8000/api"
```

**Important:** `127.0.0.1` refers to the device itself. For an Android
emulator, use the emulator's host-machine address (commonly `10.0.2.2`).
For a physical phone, use the development computer's LAN IP address and
ensure both devices can reach it. Use HTTPS for deployed environments.

## Configuration

Application-wide frontend settings are defined in `src/config.py`.

  -----------------------------------------------------------------------
  Setting                             Purpose
  ----------------------------------- -----------------------------------
  `API_BASE_URL`                      Backend API base URL

  `ALLOWED_EMAIL_DOMAIN`              Expected institutional email domain

  `OTP_LENGTH`                        Email verification code length

  `REQUEST_TIMEOUT_S`                 HTTP request timeout

  `DEV_MODE`                          Enables development shortcuts

  `ROLE_STUDENT`, `ROLE_STAFF`,       Application role identifiers
  `ROLE_ADMIN`                        
  -----------------------------------------------------------------------

The current repository configuration has `DEV_MODE = True`. Development
shortcuts should be disabled and reviewed before preparing a release
build.

The backend reads Supabase configuration from environment variables
through `backend/config.py`.

## Building the Android APK

The repository includes a `build.sh` script that invokes the Flet
Android build process:

``` bash
bash build.sh
```

The script activates an `env` virtual environment, clears the previous
build directory and runs:

``` bash
flet build apk
```

Make sure the expected `env` environment exists and contains the
required dependencies before using the script. Android build
prerequisites and permissions may also need to be configured for your
machine and Flet version.

The project manifest and `pyproject.toml` declare Android permissions
for internet access, camera and location.

## How It Works

### Authentication and session restoration

-   The backend authenticates users and returns access and refresh
    tokens.
-   The frontend session module maintains the current user and access
    token.
-   The refresh token and basic user information are persisted using
    Flet SharedPreferences.
-   On startup, the app attempts to restore the session using the saved
    refresh token.
-   The centralized API client attaches the access token to
    authenticated requests and attempts a refresh when the backend
    responds with `401 Unauthorized`.

### Reporting an issue

1.  The student selects an issue category and enters a description.
2.  The student selects a campus building and can optionally enter a
    room.
3.  The student may attach photos and allow GPS-based building
    suggestions.
4.  The frontend validates the form and submits the issue to the
    backend.
5.  The backend validates the submitted data, stores uploaded photos in
    Supabase Storage and records the issue data.

### Tracking and contacting a worker

The issue details screen retrieves complaint information from the issue
service and displays its status, timeline, comments and other available
details. If a worker has been assigned and a phone number is available,
the student can use the contact links to open the device's phone, SMS or
WhatsApp application. These links prepare the contact action; the user
must initiate the call or send the message.

## Security and Deployment Notes

-   Keep Supabase service-role credentials on the backend only.
-   Do not commit `.env` files, access tokens, refresh tokens or other
    secrets.
-   Disable development shortcuts before release.
-   Use HTTPS for deployed API communication.
-   Configure Supabase Row Level Security (RLS), storage policies and
    authentication settings appropriately.
-   Review how refresh tokens are stored locally. SharedPreferences
    persistence in the current implementation should not be treated as
    encrypted secure storage.
-   Validate email-domain restrictions and authorization on the backend;
    frontend checks alone are not a security boundary.
-   Test camera, location permissions, API connectivity and
    authentication flows on each target platform.
-   Verify the administrative workflows and backend endpoints before
    relying on them in production.

## Contributing

Contributions, bug reports and suggestions are welcome.

1.  Fork the repository.
2.  Create a feature branch.
3.  Make focused changes and test them.
4.  Open a pull request with a clear description of the changes.

Please avoid committing credentials, generated build files or local
environment configuration.
