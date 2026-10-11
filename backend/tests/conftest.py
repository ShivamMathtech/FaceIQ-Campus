import sys, io, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from cryptography.fernet import Fernet
from app.db.database import Base, make_engine, get_db
from app.core.config import get_settings
from app.core.security import hasher, limiter, issue_token
from app.models.entities import *
from app.main import app
from app.computer_vision.engine import engine

PASSWORD = "Test-only-password-123!"


@pytest.fixture(scope="session")
def password_hash():
    return hasher.hash(PASSWORD)


@pytest.fixture
def env(tmp_path, monkeypatch, password_hash):
    dbengine = make_engine("sqlite:///" + str(tmp_path / "test.db"))
    Base.metadata.create_all(dbengine)
    factory = sessionmaker(dbengine, expire_on_commit=False)

    def override():
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr("app.websocket.live.SessionLocal", factory)
    get_settings().encryption_key = Fernet.generate_key().decode()
    limiter.entries.clear()
    engine.tracks.clear()
    vector = np.zeros(128, dtype=np.float32)
    vector[0] = 1
    with factory() as db:
        users = [
            User(name=n, email=e, password_hash=password_hash, role=r)
            for n, e, r in [
                ("Admin Test", "admin@example.test", "admin"),
                ("Faculty One", "one@example.test", "faculty"),
                ("Faculty Two", "two@example.test", "faculty"),
                ("Student Login", "student@example.test", "student"),
            ]
        ]
        db.add_all(users)
        db.flush()
        tokens = {
            u.role if u.role != "faculty" else u.email.split("@")[0]: issue_token(db, u)
            for u in users
        }
        db.commit()
    with TestClient(app) as client:
        monkeypatch.setattr(engine, "detector", object())
        monkeypatch.setattr(engine, "recognizer", object())
        monkeypatch.setattr(
            engine,
            "analyze",
            lambda image: [
                {
                    "box": [20, 20, 160, 160],
                    "embedding": vector.copy(),
                    "quality_error": None,
                }
            ],
        )
        yield {
            "client": client,
            "factory": factory,
            "admin": {"Authorization": "Bearer " + tokens["admin"]},
            "faculty": {"Authorization": "Bearer " + tokens["one"]},
            "other": {"Authorization": "Bearer " + tokens["two"]},
            "student": {"Authorization": "Bearer " + tokens["student"]},
            "tokens": tokens,
            "users": users,
            "vector": vector,
            "tmp": tmp_path,
        }
    app.dependency_overrides.clear()
    dbengine.dispose()


@pytest.fixture
def image_bytes():
    arr = np.random.default_rng(42).integers(35, 215, (240, 240, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def student_body(erp="TEST001", name="Fictional Student"):
    return dict(
        name=name,
        erp_id=erp,
        email="",
        department="Computer Science",
        program="B.Tech",
        semester=4,
        section="A",
        consent=True,
    )


def course_body(code="CS301"):
    return dict(
        code=code,
        name="Data Structures",
        department="Computer Science",
        semester=4,
        section="A",
        academic_year="2026-2027",
    )


@pytest.fixture
def workflow(env, image_bytes):
    from datetime import timedelta

    c = env["client"]
    h = env["admin"]
    st = c.post("/api/students", json=student_body(), headers=h).json()
    st2 = c.post(
        "/api/students", json=student_body("TEST002", "Absent Student"), headers=h
    ).json()
    r = c.post(
        "/api/students/" + st["id"] + "/photo",
        files={"file": ("face.png", image_bytes, "image/png")},
        headers=h,
    )
    assert r.status_code == 200, r.text
    co = c.post("/api/courses", json=course_body(), headers=h).json()
    assert (
        c.post(
            "/api/courses/" + co["id"] + "/enrollments",
            json={"student_ids": [st["id"], st2["id"]]},
            headers=h,
        ).status_code
        == 200
    )
    c.post(
        "/api/faculty/assignments",
        json={"course_id": co["id"], "faculty_id": env["users"][1].id},
        headers=h,
    )
    policy = c.get("/api/settings", headers=h).json()["policy"]
    policy.update(
        calibration_approved=True,
        calibration_note="TEST ONLY: deterministic embeddings, not real-world calibration",
        smoothing_frames=2,
    )
    assert c.put("/api/settings", json=policy, headers=h).status_code == 200
    start = now() - timedelta(minutes=1)
    end = now() + timedelta(minutes=20)
    s = c.post(
        "/api/sessions",
        json=dict(
            course_id=co["id"],
            faculty_id=env["users"][1].id,
            starts_at=start.isoformat() + "Z",
            ends_at=end.isoformat() + "Z",
            room="Test Lab",
        ),
        headers=h,
    ).json()
    assert (
        c.post(
            "/api/sessions/" + s["id"] + "/start", headers=env["faculty"]
        ).status_code
        == 200
    )
    env.update(st=st, st2=st2, course=co, session=s, image=image_bytes)
    return env


def recognize(w, request_id=None, headers=None):
    return w["client"].post(
        "/api/sessions/" + w["session"]["id"] + "/recognition-events",
        headers=headers or w["faculty"],
        files={"frame": ("frame.jpg", w["image"], "image/png")},
        data={"request_id": request_id or str(uuid.uuid4())},
    )
