"""Local maintenance command; audit actor is System, not an impersonated admin."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.db.database import SessionLocal
from app.api.reporting import retention

with SessionLocal() as db:
    result = retention(None, db)
    db.commit()
    print(result)
