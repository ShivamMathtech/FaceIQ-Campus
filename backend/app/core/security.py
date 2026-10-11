import hashlib, secrets, time
from collections import OrderedDict, deque
from threading import Lock
from datetime import timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from app.db.database import get_db
from app.core.config import get_settings
from app.models.entities import User, AuthSession, now

hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)
_dummy = hasher.hash(secrets.token_urlsafe(24))


def hash_password(password):
    if len(password) < 12:
        raise HTTPException(422, "Password must contain at least 12 characters")
    return hasher.hash(password)


def verify_password(password, password_hash):
    try:
        return hasher.verify(password_hash or _dummy, password)
    except (VerificationError, InvalidHashError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def resolve_user(db, token):
    row = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash(token), AuthSession.expires_at > now()
        )
    )
    user = db.get(User, row.user_id) if row else None
    if not user or not user.active:
        raise HTTPException(401, "Session expired or invalid")
    return user


def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer), db=Depends(get_db)
):
    if not credentials:
        raise HTTPException(401, "Authentication required")
    return resolve_user(db, credentials.credentials)


def admin(user=Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Administrator role required")
    return user


def staff(user=Depends(current_user)):
    if user.role not in ("admin", "faculty"):
        raise HTTPException(403, "Staff role required")
    return user


def issue_token(db, user):
    token = secrets.token_urlsafe(40)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=now() + timedelta(minutes=get_settings().token_minutes),
        )
    )
    return token


def cipher():
    key = get_settings().encryption_key
    if not key:
        raise HTTPException(503, "Encryption key missing; run scripts/configure.py")
    return Fernet(key.encode())


class Limiter:
    def __init__(self):
        self.entries = OrderedDict()
        self.lock = Lock()

    def check(self, key, limit, seconds=60):
        with self.lock:
            t = time.monotonic()
            q = self.entries.setdefault(key, deque())
            while q and q[0] < t - seconds:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(429, "Too many requests; please wait")
            q.append(t)
            self.entries.move_to_end(key)
            while len(self.entries) > 10000:
                self.entries.popitem(last=False)


limiter = Limiter()
