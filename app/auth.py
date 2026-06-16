from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from jwt import PyJWKClient

from app.config import get_infrastructure_settings

security = HTTPBearer(auto_error=False)
TOKEN_MAX_AGE_SECONDS = 60 * 60 * 12


@dataclass(frozen=True)
class AuthUser:
    sub: str
    username: str | None = None
    email: str | None = None


def keycloak_enabled() -> bool:
    settings = get_infrastructure_settings()
    if not settings.keycloak_enabled:
        return False
    return bool(settings.keycloak_realm.strip() and settings.keycloak_client_id.strip())


def auth_required() -> bool:
    if keycloak_enabled():
        return True
    return bool(get_infrastructure_settings().admin_password.strip())


def auth_provider() -> str:
    if keycloak_enabled():
        return "keycloak"
    if auth_required():
        return "password"
    return "none"


def keycloak_public_config() -> dict[str, str] | None:
    if not keycloak_enabled():
        return None
    settings = get_infrastructure_settings()
    return {
        "url": settings.keycloak_public_url.rstrip("/"),
        "realm": settings.keycloak_realm,
        "client_id": settings.keycloak_client_id,
    }


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_infrastructure_settings().app_secret_key, salt="admin-auth")


def create_access_token() -> str:
    return _serializer().dumps({"sub": "admin", "iat": datetime.now(UTC).isoformat()})


def _verify_legacy_token(token: str) -> bool:
    try:
        _serializer().loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
        return True
    except (BadSignature, SignatureExpired):
        return False


@lru_cache
def _jwks_client() -> PyJWKClient:
    settings = get_infrastructure_settings()
    base = settings.keycloak_internal_url.rstrip("/")
    realm = settings.keycloak_realm
    jwks_url = f"{base}/realms/{realm}/protocol/openid-connect/certs"
    return PyJWKClient(jwks_url)


def _keycloak_issuer() -> str:
    settings = get_infrastructure_settings()
    return f"{settings.keycloak_public_url.rstrip('/')}/realms/{settings.keycloak_realm}"


def verify_access_token(token: str) -> bool:
    return decode_access_token(token) is not None


def decode_access_token(token: str) -> AuthUser | None:
    if keycloak_enabled():
        return _decode_keycloak_token(token)
    if _verify_legacy_token(token):
        return AuthUser(sub="admin", username="admin")
    return None


def _decode_keycloak_token(token: str) -> AuthUser | None:
    settings = get_infrastructure_settings()
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        payload: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=_keycloak_issuer(),
            options={"verify_aud": False},
        )
    except jwt.PyJWTError:
        return None

    authorized_party = payload.get("azp") or payload.get("client_id")
    if authorized_party != settings.keycloak_client_id:
        return None

    subject = str(payload.get("sub", "")).strip()
    if not subject:
        return None

    preferred_username = payload.get("preferred_username")
    email = payload.get("email")
    return AuthUser(
        sub=subject,
        username=str(preferred_username) if preferred_username else None,
        email=str(email) if email else None,
    )


def login(password: str) -> str | None:
    if keycloak_enabled():
        return None
    settings = get_infrastructure_settings()
    expected = settings.admin_password
    if not expected:
        return create_access_token()
    if secrets.compare_digest(password, expected):
        return create_access_token()
    return None


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> AuthUser | None:
    if not auth_required():
        return None
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = decode_access_token(credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
