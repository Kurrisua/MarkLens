"""Authentication, authorization and audit helpers for product APIs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .errors import AppError
from .models import AuditEvent, AuthSession, Project, ProjectMembership, User, UserRole

ROLE_USER = "user"
ROLE_OPERATOR = "operator"
ROLE_ADMIN = "admin"
VALID_ROLES = {ROLE_USER, ROLE_OPERATOR, ROLE_ADMIN}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _secret() -> bytes:
    settings = get_settings()
    if not settings.auth_secret or (
        settings.app_env != "development"
        and settings.auth_secret == "marklens-development-only-change-me"
    ):
        raise RuntimeError("AUTH_SECRET must be configured outside development")
    return settings.auth_secret.encode()


def hash_password(password: str) -> str:
    """Use Argon2id when installed; scrypt remains a secure development fallback."""
    try:
        from argon2 import PasswordHasher

        return "argon2$" + PasswordHasher().hash(password)
    except ImportError:
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return f"scrypt${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, payload = encoded.split("$", 1)
    except ValueError:
        return False
    if scheme == "argon2":
        try:
            from argon2 import PasswordHasher
            from argon2.exceptions import VerifyMismatchError

            try:
                return PasswordHasher().verify(payload, password)
            except VerifyMismatchError:
                return False
        except ImportError:
            return False
    if scheme == "scrypt":
        try:
            _, salt_text, digest_text = encoded.split("$", 2)
            actual = hashlib.scrypt(password.encode(), salt=_unb64(salt_text), n=2**14, r=8, p=1)
            return hmac.compare_digest(actual, _unb64(digest_text))
        except (TypeError, ValueError):
            return False
    return False


def create_access_token(user: User, roles: set[str]) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": user.id,
        "roles": sorted(roles),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=get_settings().access_token_minutes)).timestamp()),
    }
    encoded = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64(hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest())
    return f"ml1.{encoded}.{signature}"


def decode_access_token(token: str) -> dict[str, object]:
    try:
        version, encoded, signature = token.split(".")
        expected = _b64(hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest())
        if version != "ml1" or not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(_unb64(encoded))
        if int(payload["exp"]) <= int(datetime.utcnow().timestamp()):
            raise ValueError
        return payload
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise AppError(401, "AUTHENTICATION_REQUIRED", "登录状态已失效，请重新登录。") from None


def issue_refresh_token(session: Session, user: User, user_agent: str | None = None) -> str:
    raw_token = secrets.token_urlsafe(48)
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(days=get_settings().refresh_token_days),
            user_agent=(user_agent or "")[:500] or None,
        )
    )
    return raw_token


def consume_refresh_token(session: Session, raw_token: str) -> User:
    item = session.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
        )
    )
    if item is None or item.revoked_at is not None or item.expires_at <= datetime.utcnow():
        raise AppError(401, "REFRESH_TOKEN_INVALID", "登录状态已失效，请重新登录。")
    user = session.get(User, item.user_id)
    if user is None or user.status != "active":
        raise AppError(401, "AUTHENTICATION_REQUIRED", "账号不可用，请联系管理员。")
    item.revoked_at = datetime.utcnow()
    return user


def roles_for(session: Session, user_id: str) -> set[str]:
    return set(session.scalars(select(UserRole.role).where(UserRole.user_id == user_id)).all()) or {
        ROLE_USER
    }


class CurrentUser:
    def __init__(self, user: User, roles: set[str]) -> None:
        self.user = user
        self.roles = roles

    @property
    def is_admin(self) -> bool:
        return ROLE_ADMIN in self.roles


def current_user(
    authorization: Annotated[str | None, Header()] = None,
    session: Session = Depends(get_db),
) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(401, "AUTHENTICATION_REQUIRED", "请登录后继续操作。")
    payload = decode_access_token(authorization.removeprefix("Bearer "))
    user_id = str(payload.get("sub", ""))
    user = session.get(User, user_id)
    if user is None or user.status != "active":
        raise AppError(401, "AUTHENTICATION_REQUIRED", "登录状态已失效，请重新登录。")
    return CurrentUser(user, roles_for(session, user.id))


def require_roles(*allowed_roles: str):
    def dependency(actor: CurrentUser = Depends(current_user)) -> CurrentUser:
        if not actor.roles.intersection(allowed_roles):
            raise AppError(403, "PERMISSION_DENIED", "你没有访问此功能的权限。")
        return actor

    return dependency


def require_project_access(session: Session, project_id: str, actor: CurrentUser) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "品牌项目不存在。")
    if actor.is_admin or project.owner_id == actor.user.id:
        return project
    membership = session.scalar(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project.id,
            ProjectMembership.user_id == actor.user.id,
        )
    )
    if membership is None:
        raise AppError(403, "PERMISSION_DENIED", "你无权访问此品牌项目。")
    return project


def audit(
    session: Session,
    request: Request,
    actor: CurrentUser | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_id=actor.user.id if actor else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=getattr(request.state, "request_id", None),
            details=details or {},
        )
    )
