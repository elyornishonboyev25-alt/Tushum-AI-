"""Password hashing and revocable, expiring bearer sessions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import time

from fastapi import Header, HTTPException

from . import database
from .domain import now


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32
        )
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(connection, user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    connection.execute("DELETE FROM sessions WHERE expires_at<?", (now(),))
    connection.execute(
        "INSERT INTO sessions VALUES (?,?,?,?)", (token_hash(token), user_id, expires, now())
    )
    return token


def current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Davom etish uchun akkauntingizga kiring.")
    with database.read() as connection:
        user = connection.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1",
            (token_hash(authorization[7:]), now()),
        ).fetchone()
    if user is None:
        raise HTTPException(401, "Sessiya yakunlandi. Qayta kiring.")
    return dict(user)


def check_attempts(identifier: str) -> None:
    cutoff = int(time.time()) - 600
    with database.write() as connection:
        connection.execute("DELETE FROM login_attempts WHERE attempted_at<?", (cutoff,))
        count = connection.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE identifier=?", (identifier,)
        ).fetchone()[0]
        if count >= 12:
            raise HTTPException(
                429, "Urinishlar ko‘paydi. 10 daqiqadan keyin qayta urinib ko‘ring."
            )
        connection.execute(
            "INSERT INTO login_attempts(identifier,attempted_at) VALUES (?,?)",
            (identifier, int(time.time())),
        )
