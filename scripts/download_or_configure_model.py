"""Download official, pinned OpenCV Zoo artifacts and verify LFS SHA-256."""

import hashlib, json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "model-manifest.json").read_text())
folder = ROOT / "storage" / "models"
folder.mkdir(parents=True, exist_ok=True)
for m in manifest["models"]:
    path = folder / m["file"]
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == m["sha256"]:
        print("Verified:", m["file"])
        continue
    url = f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{manifest['revision']}/models/{m['directory']}/{m['file']}"
    print("Downloading official model:", m["file"])
    try:
        with urllib.request.urlopen(url, timeout=120) as source:
            data = source.read(m["size"] + 1)
        if len(data) != m["size"] or hashlib.sha256(data).hexdigest() != m["sha256"]:
            raise ValueError("SHA-256 or size mismatch; refusing model")
        tmp = path.with_suffix(".download")
        tmp.write_bytes(data)
        tmp.replace(path)
        license_url = f"https://raw.githubusercontent.com/opencv/opencv_zoo/{manifest['revision']}/models/{m['directory']}/LICENSE"
        (folder / (m["directory"] + "-LICENSE.txt")).write_bytes(
            urllib.request.urlopen(license_url, timeout=30).read()
        )
        print("Verified SHA-256:", m["file"])
    except Exception as e:
        print(
            "Model setup failed:",
            e,
            "\nManagement and manual attendance remain available. Retry when online.",
        )
        sys.exit(1)
print("Restart backend. Upload or regenerate templates, then calibrate the threshold.")
