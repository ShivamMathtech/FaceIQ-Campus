from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from alembic.config import Config
from alembic import command

(ROOT / "storage").mkdir(exist_ok=True)
command.upgrade(Config(str(ROOT / "backend" / "alembic.ini")), "head")
print("Database migrations applied. Existing records preserved.")
