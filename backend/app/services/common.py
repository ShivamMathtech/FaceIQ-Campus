from sqlalchemy import select, func
from fastapi import HTTPException
from app.models.entities import *
from app.schemas.contracts import Policy


def require(db, cls, id):
    obj = db.get(cls, id)
    if not obj:
        raise HTTPException(404, "Resource not found")
    return obj


def audit(db, user, action, resource, details=None):
    db.add(
        AuditLog(
            actor_id=user.id if user else None,
            action=action,
            resource_id=resource,
            details=details or {},
        )
    )


def policy(db):
    obj = db.get(ApplicationSetting, "attendance_policy")
    return Policy(**(obj.value if obj else {})).model_dump()


def course_scope(db, user, course_id):
    c = require(db, Course, course_id)
    if user.role == "admin":
        return c
    if user.role == "faculty":
        allowed = db.scalar(
            select(FacultyCourseAssignment.id).where(
                FacultyCourseAssignment.course_id == course_id,
                FacultyCourseAssignment.faculty_id == user.id,
            )
        )
    else:
        allowed = db.scalar(
            select(CourseEnrollment.id)
            .join(Student, Student.id == CourseEnrollment.student_id)
            .where(CourseEnrollment.course_id == course_id, Student.user_id == user.id)
        )
    if not allowed:
        raise HTTPException(403, "Not authorized for this course")
    return c


def session_scope(db, user, id, write=False):
    s = require(db, AttendanceSession, id)
    course_scope(db, user, s.course_id)
    if write and (
        user.role == "student" or (user.role == "faculty" and s.faculty_id != user.id)
    ):
        raise HTTPException(403, "Not assigned to this session")
    return s


def lock_session(db, id):
    return db.scalar(
        select(AttendanceSession)
        .where(AttendanceSession.id == id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def user_view(u):
    return {k: getattr(u, k) for k in ("id", "name", "email", "role", "active")}


def student_view(s):
    return {
        **{
            k: getattr(s, k)
            for k in (
                "id",
                "name",
                "erp_id",
                "email",
                "department",
                "program",
                "semester",
                "section",
                "active",
                "consent",
                "consent_at",
                "biometric_status",
                "updated_at",
                "user_id",
            )
        },
        "has_photo": bool(s.photo),
    }


def columns(o, exclude=()):
    return {
        c.name: getattr(o, c.name) for c in o.__table__.columns if c.name not in exclude
    }


def visible_courses(db, user):
    q = select(Course.id)
    if user.role == "faculty":
        q = q.join(FacultyCourseAssignment).where(
            FacultyCourseAssignment.faculty_id == user.id
        )
    if user.role == "student":
        q = q.join(CourseEnrollment).join(Student).where(Student.user_id == user.id)
    return q


def own_student(db, user):
    s = db.scalar(select(Student).where(Student.user_id == user.id))
    if not s:
        raise HTTPException(403, "No linked student profile")
    return s
