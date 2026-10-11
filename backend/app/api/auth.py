from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, delete
from app.db.database import get_db
from app.core.security import *
from app.schemas.contracts import Login
from app.models.entities import AuditLog
from app.services.common import user_view, audit

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login")
def login(body: Login, request: Request, db=Depends(get_db)):
    limiter.check(("login", request.client.host), 10, 60)
    limiter.check(("account", body.email.lower()), 10, 60)
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    valid = verify_password(body.password, u.password_hash if u else None)
    if not valid or not u or not u.active:
        raise HTTPException(401, "Invalid email or password")
    token = issue_token(db, u)
    audit(db, u, "LOGIN", u.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": get_settings().token_minutes * 60,
        "user": user_view(u),
    }


@router.get("/me")
def me(user=Depends(current_user)):
    return user_view(user)


@router.post("/logout")
def logout(credentials=Depends(bearer), user=Depends(current_user), db=Depends(get_db)):
    db.execute(
        delete(AuthSession).where(
            AuthSession.token_hash == token_hash(credentials.credentials)
        )
    )
    audit(db, user, "LOGOUT", user.id)
    return {"ok": True}
