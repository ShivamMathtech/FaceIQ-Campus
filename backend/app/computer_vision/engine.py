"""CPU-only YuNet/SFace; no fallback identity, no production mock adapter."""

import io, json, hashlib, time
from pathlib import Path
from threading import Lock
from collections import OrderedDict
import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException
from app.core.config import get_settings

MODEL_VERSION = "opencv-sface-2021dec-v1"
Image.MAX_IMAGE_PIXELS = 12_000_000


def decode_image(data, enrollment=False):
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "Image exceeds upload limit")
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ("JPEG", "PNG"):
                raise HTTPException(422, "Only JPEG and PNG image content is accepted")
            if img.width * img.height > 12_000_000:
                raise HTTPException(422, "Image must be below 12 megapixels")
            if min(img.size) < (160 if enrollment else 64):
                raise HTTPException(
                    422,
                    "Image dimensions are too small; enrollment requires at least 160 x 160",
                )
            img = ImageOps.exif_transpose(img).convert("RGB")
            img.thumbnail((1600, 1600))
            arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)  # Remove metadata.
            return arr, buf.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(422, "Invalid or oversized image file")


def quality(face):
    if face.size == 0 or min(face.shape[:2]) < 70:
        return "Move closer; face must be at least 70 pixels wide and high"
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    if not 40 <= float(gray.mean()) <= 220:
        return "Improve even lighting; face is too dark or overexposed"
    if cv2.Laplacian(gray, cv2.CV_64F).var() < 35:
        return "Face is blurred; hold still and focus the camera"
    return None


def normalize(v):
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    if v.size != 128 or not np.isfinite(v).all() or np.linalg.norm(v) < 1e-8:
        raise ValueError("Invalid SFace embedding")
    return v / np.linalg.norm(v)


def match_embedding(vector, candidates, threshold, margin):
    if not candidates:
        return "UNKNOWN_FACE", None, None
    scores = sorted(
        ((float(np.dot(vector, v)), sid) for sid, v in candidates), reverse=True
    )
    best, sid = scores[0]
    if best < threshold:
        return (
            ("LOW_CONFIDENCE" if best >= threshold - 0.1 else "UNKNOWN_FACE"),
            None,
            best,
        )
    if len(scores) > 1 and best - scores[1][0] < margin:
        return "MULTIPLE_CANDIDATES", None, best
    return "MATCH", sid, best


class FaceEngine:
    def __init__(self):
        self.lock = Lock()
        self.detector = None
        self.recognizer = None
        self.message = "Model setup required"
        self.tracks = OrderedDict()

    def load(self):
        root = Path(get_settings().model_dir)
        manifest = Path(__file__).resolve().parents[3] / "model-manifest.json"
        try:
            spec = json.loads(manifest.read_text())
            for model in spec["models"]:
                path = root / model["file"]
                if (
                    not path.exists()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != model["sha256"]
                ):
                    raise ValueError("Missing or unverified model: " + model["file"])
            cv2.setNumThreads(get_settings().cv_threads)
            self.detector = cv2.FaceDetectorYN.create(
                str(root / spec["models"][0]["file"]), "", (320, 320), 0.9, 0.3, 5000
            )
            self.recognizer = cv2.FaceRecognizerSF.create(
                str(root / spec["models"][1]["file"]), ""
            )
            self.message = "CPU recognition ready; threshold calibration required before automatic marking"
        except (OSError, ValueError, cv2.error) as e:
            self.detector = None
            self.recognizer = None
            self.message = str(e)

    @property
    def available(self):
        return self.detector is not None and self.recognizer is not None

    def status(self):
        return {
            "available": self.available,
            "message": self.message,
            "model": MODEL_VERSION,
            "liveness": "UNAVAILABLE",
            "inference_interval_ms": get_settings().inference_interval_ms,
            "max_width": get_settings().frame_max_width,
        }

    def analyze(self, image):
        if not self.available:
            raise HTTPException(503, "Recognition setup required: " + self.message)
        if not self.lock.acquire(blocking=False):
            raise HTTPException(429, "Recognition worker is busy; retry next sample")
        try:
            h, w = image.shape[:2]
            scale = min(1, get_settings().frame_max_width / w)
            resized = (
                cv2.resize(image, (round(w * scale), round(h * scale)))
                if scale < 1
                else image
            )
            self.detector.setInputSize((resized.shape[1], resized.shape[0]))
            _, faces = self.detector.detect(resized)
            out = []
            for face in [] if faces is None else faces[:10]:
                x, y, fw, fh = face[:4]
                x0 = max(0, int(x))
                y0 = max(0, int(y))
                x1 = min(resized.shape[1], int(x + fw))
                y1 = min(resized.shape[0], int(y + fh))
                error = quality(resized[y0:y1, x0:x1])
                feature = (
                    None
                    if error
                    else normalize(
                        self.recognizer.feature(
                            self.recognizer.alignCrop(resized, face)
                        )
                    )
                )
                out.append(
                    {
                        "box": [round(float(v) / scale, 1) for v in face[:4]],
                        "embedding": feature,
                        "quality_error": error,
                    }
                )
            return out
        finally:
            self.lock.release()

    def enroll(self, image):
        faces = self.analyze(image)
        if len(faces) != 1:
            raise HTTPException(
                422, "Enrollment requires exactly one clearly visible face"
            )
        if faces[0]["quality_error"]:
            raise HTTPException(422, faces[0]["quality_error"])
        return faces[0]["embedding"]

    def retain_session_tracks(self, session_id, matched_ids):
        with self.lock:
            for key in list(self.tracks):
                if key[0] == session_id and key[1] not in matched_ids:
                    del self.tracks[key]

    def smooth(self, session_id, student_id, box, required):
        # Short-term identity + position tracking, bounded and reset on long gaps.
        with self.lock:
            key = (session_id, student_id)
            t = time.monotonic()
            old = self.tracks.get(key)
            count = 1
            if (
                old
                and t - old[0] < 3
                and abs(box[0] - old[2][0]) < max(box[2], old[2][2])
                and abs(box[1] - old[2][1]) < max(box[3], old[2][3])
            ):
                count = old[1] + 1
            self.tracks[key] = (t, count, box)
            self.tracks.move_to_end(key)
            while len(self.tracks) > 2000:
                self.tracks.popitem(last=False)
            return count >= required


engine = FaceEngine()
