from __future__ import annotations

import base64
import json
import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional

from passlib.context import CryptContext

from ..models import UserRole
from ..schemas import TokenData

SECRET_KEY = "change-me-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


class JWTError(Exception):
    """Minimal JWT error used when token validation fails."""


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _urlsafe_b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _normalise_claim(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return int(value.replace(tzinfo=timezone.utc).timestamp())
    return value


def _build_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _normalise_claim(value) for key, value in data.items()}


def _sign(parts: list[str]) -> str:
    signing_input = ".".join(parts).encode("ascii")
    signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return _urlsafe_b64encode(signature)


def create_access_token(
    *, data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = _build_payload(data.copy())
    expire = datetime.utcnow() + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    now = datetime.utcnow()
    to_encode.update({
        "exp": int(expire.replace(tzinfo=timezone.utc).timestamp()),
        "iat": int(now.replace(tzinfo=timezone.utc).timestamp()),
    })
    header = {"alg": ALGORITHM, "typ": "JWT"}
    header_segment = _urlsafe_b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _urlsafe_b64encode(
        json.dumps(to_encode, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature_segment = _sign([header_segment, payload_segment])
    return ".".join([header_segment, payload_segment, signature_segment])


def decode_token(token: str) -> TokenData:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise JWTError("Invalid token structure") from exc

    expected_signature = _sign([header_segment, payload_segment])
    actual_signature = signature_segment
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise JWTError("Invalid token signature")

    try:
        payload_bytes = _urlsafe_b64decode(payload_segment)
        payload = json.loads(payload_bytes)
    except (ValueError, json.JSONDecodeError) as exc:
        raise JWTError("Invalid token payload") from exc

    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        raise JWTError("Token missing expiration")
    if datetime.utcnow().timestamp() > float(exp):
        raise JWTError("Token has expired")

    uni = payload.get("sub")
    if not isinstance(uni, str) or not uni:
        raise JWTError("Invalid token payload")

    role_value = payload.get("role")
    try:
        role = UserRole(role_value) if role_value else None
    except ValueError as exc:
        raise JWTError("Invalid role in token") from exc

    return TokenData(uni=uni, role=role)
