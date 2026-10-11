"""Explicit fictional seed. No images, templates, recognition or attendance generated."""

from pathlib import Path
import sys, getpass
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.db.database import SessionLocal
from app.models.entities import *
from app.core.security import hash_password
from sqlalchemy import select

password = getpass.getpass(
    "Choose a 12+ character password for fictional faculty demo account: "
)
password_hash = hash_password(password)
with SessionLocal() as db:
    if db.scalar(select(Course).where(Course.code == "DEMO-CS301")):
        sys.exit("Demo course exists; no records changed.")
    faculty = User(
        name="Dr. Avery Demo (Fictional)",
        email="faculty.demo@example.test",
        password_hash=password_hash,
        role="faculty",
    )
    db.add(faculty)
    db.flush()
    course = Course(
        code="DEMO-CS301",
        name="Data Structures — Fictional Demo",
        department="Computer Science",
        semester=4,
        section="A",
        academic_year="2026-2027",
    )
    db.add(course)
    db.flush()
    db.add(FacultyCourseAssignment(course_id=course.id, faculty_id=faculty.id))
    for i, name in enumerate(
        [
            "Alex Demo",
            "Sam Example",
            "Taylor Sample",
            "Morgan Fiction",
            "Riley Demo",
            "Casey Example",
        ],
        1,
    ):
        s = Student(
            name=name + " (Fictional)",
            erp_id=f"DEMO{i:04}",
            email="",
            department="Computer Science",
            program="B.Tech",
            semester=4,
            section="A",
            consent=False,
        )
        db.add(s)
        db.flush()
        db.add(CourseEnrollment(course_id=course.id, student_id=s.id))
    db.add(
        AttendanceSession(
            course_id=course.id,
            faculty_id=faculty.id,
            starts_at=now(),
            ends_at=now() + timedelta(hours=1),
            room="Demo Room — Fictional",
        )
    )
    db.add(
        AuditLog(
            action="DEMO_DATA_CREATED",
            resource_id=course.id,
            details={"synthetic": True, "attendance_generated": False},
        )
    )
    db.commit()
print(
    "Fictional data created. Faculty email: faculty.demo@example.test; password is the one you chose."
)
print(
    "No synthetic face identities or attendance results were generated. Use administrator manual corrections to test attendance."
)
