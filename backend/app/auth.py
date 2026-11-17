from __future__ import annotations
"""
Zero-Dependency Cryptographic JWT & RBAC Authentication Module.
Uses standard library HMAC-SHA256 + PBKDF2-HMAC-SHA256 so it works identically
across Python 3.11 / 3.12 / 3.13 without fragile C-extension conflicts.
"""
import base64
import hashlib
import hmac
import json
import time
import secrets
from typing import Any, Dict, Optional
from .config import settings


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Store a PBKDF2 hash with a unique per-password salt."""
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 310_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, expected_hash: str, salt: Optional[str] = None) -> bool:
    try:
        stored_salt, stored_digest = expected_hash.split("$", 1)
    except ValueError:
        # Compatibility for older demo hashes; migrate before production use.
        stored_salt, stored_digest = salt or "claimwise-demo-seed-salt", expected_hash
    computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), stored_salt.encode("utf-8"), 310_000).hex()
    return hmac.compare_digest(computed, stored_digest)


def create_jwt_token(payload: Dict[str, Any], expires_in_seconds: int = 86400) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    body = {**payload, "iat": now, "exp": now + expires_in_seconds}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    body_b64 = _b64url_encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{body_b64}".encode("ascii")
    signature = hmac.new(
        settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(signature)
    return f"{header_b64}.{body_b64}.{sig_b64}"


def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, body_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{body_b64}".encode("ascii")
        expected_sig = hmac.new(
            settings.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256
        ).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(body_b64).decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


SEED_USERS: Dict[str, Dict[str, Any]] = {
    "roshan@claimwise.demo": {
        "user_id": "USR-OFF-001",
        "email": "roshan@claimwise.demo",
        "full_name": "Roshan Singh",
        "role": "officer",
        "title": "Claims Operations Lead",
        "department": "Claims Operations · Demo Workspace",
        "password_hash": hash_password("DemoOfficer@2026"),
    },
    "asha.rao@example.in": {
        "user_id": "USR-POL-102",
        "email": "asha.rao@example.in",
        "full_name": "Asha Rao",
        "role": "policyholder",
        "title": "Policyholder (Health & Motor)",
        "department": "Customer Portal",
        "password_hash": hash_password("Policy@2026"),
    },
    "priya@claimwise.demo": {
        "user_id": "USR-SIU-007",
        "email": "priya@claimwise.demo",
        "full_name": "Priya Nair",
        "role": "siu_investigator",
        "title": "Principal SIU Fraud Investigator",
        "department": "Special Investigations Unit",
        "password_hash": hash_password("SIU@2026"),
    },
}


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    user = SEED_USERS.get((email or "").strip().lower())
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    user_public = {k: v for k, v in user.items() if k != "password_hash"}
    token = create_jwt_token(user_public)
    return {"access_token": token, "token_type": "bearer", "user": user_public}

