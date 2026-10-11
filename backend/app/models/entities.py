import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    UniqueConstraint,
    LargeBinary,
    JSON,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Entity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class User(Entity, Base):
    __tablename__ = "users"
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("role IN ('admin','faculty','student')"),)


class AuthSession(Entity, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Student(Entity, Base):
    __tablename__ = "students"
    name: Mapped[str] = mapped_column(String(120))
    erp_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), default="")
    department: Mapped[str] = mapped_column(String(100))
    program: Mapped[str] = mapped_column(String(100))
    semester: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consent_notice: Mapped[str] = mapped_column(
        String(80), default="FaceIQ biometric notice v1"
    )
    photo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    photo_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    biometric_status: Mapped[str] = mapped_column(String(40), default="NOT_REGISTERED")
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class BiometricTemplate(Entity, Base):
    __tablename__ = "biometric_templates"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(80))
    encrypted_embedding: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("student_id", "version"),)


class Course(Entity, Base):
    __tablename__ = "courses"
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(100))
    semester: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(20))
    academic_year: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("code", "section", "academic_year"),)


class CourseEnrollment(Entity, Base):
    __tablename__ = "course_enrollments"
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    __table_args__ = (UniqueConstraint("course_id", "student_id"),)


class FacultyCourseAssignment(Entity, Base):
    __tablename__ = "faculty_course_assignments"
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    faculty_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    __table_args__ = (UniqueConstraint("course_id", "faculty_id"),)


class AttendanceSession(Entity, Base):
    __tablename__ = "attendance_sessions"
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    faculty_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    room: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="SCHEDULED", index=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    __table_args__ = (
        CheckConstraint("status IN ('SCHEDULED','ACTIVE','COMPLETED','CANCELLED')"),
        CheckConstraint("ends_at > starts_at"),
    )


class SessionRoster(Entity, Base):
    __tablename__ = "session_rosters"
    session_id: Mapped[str] = mapped_column(
        ForeignKey("attendance_sessions.id"), index=True
    )
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    __table_args__ = (UniqueConstraint("session_id", "student_id"),)


class AttendanceRecord(Entity, Base):
    __tablename__ = "attendance_records"
    session_id: Mapped[str] = mapped_column(
        ForeignKey("attendance_sessions.id"), index=True
    )
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    source: Mapped[str] = mapped_column(String(16))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    __table_args__ = (
        UniqueConstraint(
            "session_id", "student_id", name="uq_attendance_session_student"
        ),
        CheckConstraint("status IN ('PRESENT','LATE','ABSENT','EXCUSED','REVIEW')"),
    )


class RecognitionEvent(Entity, Base):
    __tablename__ = "recognition_events"
    session_id: Mapped[str] = mapped_column(
        ForeignKey("attendance_sessions.id"), index=True
    )
    student_id: Mapped[str | None] = mapped_column(
        ForeignKey("students.id"), nullable=True
    )
    request_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    __table_args__ = (UniqueConstraint("session_id", "request_id"),)


class AuditLog(Entity, Base):
    __tablename__ = "audit_logs"
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_id: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class ApplicationSetting(Base):
    __tablename__ = "application_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
