from pathlib import Path
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
(ROOT / "storage" / "models").mkdir(parents=True, exist_ok=True)
path = ROOT / "backend" / ".env"
if not path.exists():
    path.write_text(
        "ENCRYPTION_KEY="
        + Fernet.generate_key().decode()
        + "\nALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173\nENVIRONMENT=development\n",
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass
    print(
        "Created backend/.env with a random encryption key. Back it up securely; never commit it."
    )
else:
    print("Existing configuration preserved.")
