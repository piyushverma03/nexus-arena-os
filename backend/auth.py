"""
auth.py ─ JWT authentication utilities.
"""
from __future__ import annotations
import os
import time
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.database import get_conn

load_dotenv()
# Secret key loaded from environment — never hardcoded in source.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", os.urandom(32).hex())
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8   # Reduced to 8h for tighter sessions

# Brute-force protection: track failed login attempts per email.
# { email: {"count": int, "locked_until": float} }
_failed_attempts: dict = {}
MAX_ATTEMPTS = 5          # Max allowed failures before lockout
LOCKOUT_SECONDS = 60      # Lockout duration

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/employee/login", auto_error=False)


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Dependency helpers ─────────────────────────────────────────────────────────

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_token(token)


def require_employee(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") not in ("admin", "staff"):
        raise HTTPException(status_code=403, detail="Employee access required")
    return current_user


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── Login helpers ──────────────────────────────────────────────────────────────

def check_brute_force(email: str):
    """Raise 429 if the email is currently locked out."""
    entry = _failed_attempts.get(email)
    if entry and entry["count"] >= MAX_ATTEMPTS:
        remaining = entry["locked_until"] - time.time()
        if remaining > 0:
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed attempts. Try again in {int(remaining)}s.",
            )
        else:
            # Lock has expired — reset counter
            _failed_attempts.pop(email, None)


def record_failed_attempt(email: str):
    entry = _failed_attempts.setdefault(email, {"count": 0, "locked_until": 0})
    entry["count"] += 1
    if entry["count"] >= MAX_ATTEMPTS:
        entry["locked_until"] = time.time() + LOCKOUT_SECONDS


def clear_failed_attempts(email: str):
    _failed_attempts.pop(email, None)


def authenticate_employee(email: str, password: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM employees WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    if row and verify_password(password, row["password_hash"]):
        clear_failed_attempts(email)   # Reset on success
        return dict(row)
    record_failed_attempt(email)       # Track on failure
    return None


def authenticate_attendee(ticket_code: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM tickets WHERE ticket_code = ?", (ticket_code,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
