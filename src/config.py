"""App-wide constants. Change values here, not inside screens."""

API_BASE_URL = "https://campus-care-sl.vercel.app/api"   # Android emulator -> your PC. On a real phone use your PC's LAN IP.
# API_BASE_URL = "http://localhost:8000/api"    # local uvicorn (plain http, no TLS). Android emulator: http://10.0.2.2:8000/api; real phone: your PC LAN IP.

ALLOWED_EMAIL_DOMAIN = "iitb.ac.in"          # server must enforce this too; the server check is the real one
OTP_LENGTH = 6
REQUEST_TIMEOUT_S = 15

DEV_MODE = True   # shows dev shortcuts (skip login). Set False for release builds.

ROLE_STUDENT = "student"
ROLE_STAFF = "staff"
ROLE_ADMIN = "pho_admin"               # value of public.profiles.role for PHO admins (DB check constraint)
STAFF_ROLES = {ROLE_ADMIN, ROLE_STAFF, "admin"}   # roles that get the PHO/admin side (screens/admin/)