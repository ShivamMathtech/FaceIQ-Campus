import numpy as np
from sqlalchemy import select, func
from app.core.security import cipher
from app.models.entities import BiometricTemplate, now
from app.services.common import audit
from app.computer_vision.engine import engine, MODEL_VERSION, decode_image, normalize


def delete_biometrics(db, student, user, reason="WITHDRAWAL"):
    for t in db.scalars(
        select(BiometricTemplate).where(BiometricTemplate.student_id == student.id)
    ):
        t.active = False
        t.encrypted_embedding = None
    student.photo = None
    student.photo_updated_at = None
    student.biometric_status = "DELETED"
    student.consent = False
    audit(db, user, "BIOMETRIC_DELETED", student.id, {"reason": reason})


def register_photo(db, student, data, user):
    image, clean = decode_image(data, enrollment=True)
    embedding = engine.enroll(image) if engine.available else None
    c = cipher()
    for old in db.scalars(
        select(BiometricTemplate).where(BiometricTemplate.student_id == student.id)
    ):
        old.active = False
        old.encrypted_embedding = None
    student.photo = c.encrypt(clean)
    student.photo_updated_at = now()
    student.biometric_status = "READY" if embedding is not None else "SETUP_REQUIRED"
    if embedding is not None:
        version = (
            db.scalar(
                select(func.max(BiometricTemplate.version)).where(
                    BiometricTemplate.student_id == student.id
                )
            )
            or 0
        ) + 1
        db.add(
            BiometricTemplate(
                student_id=student.id,
                version=version,
                model=MODEL_VERSION,
                encrypted_embedding=c.encrypt(embedding.astype(np.float32).tobytes()),
            )
        )
    audit(
        db,
        user,
        "PHOTO_REPLACED",
        student.id,
        {
            "status": student.biometric_status,
            "quality_validated": embedding is not None,
        },
    )
    db.flush()


def template_vector(t):
    return normalize(
        np.frombuffer(cipher().decrypt(t.encrypted_embedding), dtype=np.float32)
    )
