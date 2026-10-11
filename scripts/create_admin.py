from pathlib import Path
import sys, getpass, re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.db.database import SessionLocal
from app.models.entities import User
from app.core.security import hash_password
from sqlalchemy import select

name = input("Administrator full name: ").strip()
email = input("Administrator email: ").strip().lower()
if len(name) < 2 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
    sys.exit("Valid name and email required.")
password = getpass.getpass("Password (12+ characters): ")
if password != getpass.getpass("Confirm password: "):
    sys.exit("Passwords did not match.")
with SessionLocal() as db:
    if db.scalar(select(User).where(User.email == email)):
        sys.exit("Email already registered.")
    db.add(
        User(
            name=name, email=email, password_hash=hash_password(password), role="admin"
        )
    )
    db.commit()
print("Administrator created. No default password is installed.")
