"""
auth.py ─ JWT authentication utilities.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.database import get_conn

SECRET_KEY = "nexus-arena-os-super-secret-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

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

def authenticate_employee(email: str, password: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM employees WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    if row and verify_password(password, row["password_hash"]):
        return dict(row)
    return None


def authenticate_attendee(ticket_code: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM tickets WHERE ticket_code = ?", (ticket_code,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
