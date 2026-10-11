"""SQLite online backup. Store backup and encryption key separately and securely."""

import argparse, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import get_settings
from sqlalchemy.engine import make_url

p = argparse.ArgumentParser()
p.add_argument("destination")
args = p.parse_args()
url = make_url(get_settings().database_url)
if url.get_backend_name() != "sqlite":
    sys.exit("For PostgreSQL, use pg_dump as documented.")
path = Path(args.destination).resolve()
if path.exists():
    sys.exit("Destination exists; refusing overwrite.")
path.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(url.database) as source, sqlite3.connect(path) as dest:
    source.backup(dest)
print("Consistent SQLite backup written:", path)
