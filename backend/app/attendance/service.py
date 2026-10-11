from datetime import timedelta
from sqlalchemy import select, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import HTTPException
from app.models.entities import *
from app.services.common import lock_session, policy, audit


def safe_insert(db, cls, values, keys):
    dialect = db.bind.dialect.name
    stmt = (
        (sqlite_insert if dialect == "sqlite" else pg_insert)(cls)
        .values(**values)
        .on_conflict_do_nothing(index_elements=keys)
    )
    return db.execute(stmt).rowcount == 1


def event(db, sid, request_id, status, student_id=None, score=None):
    safe_insert(
        db,
        RecognitionEvent,
        dict(
            id=uid(),
            created_at=now(),
            session_id=sid,
            request_id=request_id,
            status=status,
            student_id=student_id,
            score=score,
        ),
        ["session_id", "request_id"],
    )
    db.flush()
    return db.scalar(
        select(RecognitionEvent).where(
            RecognitionEvent.session_id == sid,
            RecognitionEvent.request_id == request_id,
        )
    )


def verify_attendance(db, session_id, student_id, request_id, score):
    """Internal verified-result boundary. Never exposed as a client identity endpoint."""
    s = lock_session(db, session_id)
    if not s or s.status != "ACTIVE" or now() > s.ends_at:
        raise HTTPException(409, "Attendance window is closed")
    prior = db.scalar(
        select(RecognitionEvent).where(
            RecognitionEvent.session_id == s.id,
            RecognitionEvent.request_id == request_id,
        )
    )
    if prior:
        return prior
    st = db.scalar(
        select(Student)
        .where(Student.id == student_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    eligible = db.scalar(
        select(SessionRoster.id).where(
            SessionRoster.session_id == s.id, SessionRoster.student_id == student_id
        )
    )
    # Roster frozen at start, but withdrawals/deactivation take effect immediately.
    enrolled = db.scalar(
        select(CourseEnrollment.id).where(
            CourseEnrollment.course_id == s.course_id,
            CourseEnrollment.student_id == student_id,
        )
    )
    if not eligible or not enrolled or not st or not st.active or not st.consent:
        return event(db, s.id, request_id, "NOT_ENROLLED")
    late = now() > s.starts_at + timedelta(minutes=s.policy["late_grace_minutes"])
    inserted = safe_insert(
        db,
        AttendanceRecord,
        dict(
            id=uid(),
            created_at=now(),
            session_id=s.id,
            student_id=student_id,
            status="LATE" if late else "PRESENT",
            source="FACE",
            recorded_at=now(),
            updated_at=now(),
        ),
        ["session_id", "student_id"],
    )
    existing = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == s.id,
            AttendanceRecord.student_id == student_id,
        )
    )
    status = (
        "PRESENT_RECORDED"
        if inserted
        else (
            "ALREADY_PRESENT"
            if existing.status in ("PRESENT", "LATE")
            else "REVIEW_REQUIRED"
        )
    )
    return event(db, s.id, request_id, status, student_id, score)


def finalize(db, s, user):
    s = lock_session(db, s.id)
    if s.status == "COMPLETED":
        return s
    if s.status != "ACTIVE":
        raise HTTPException(409, "Only an active session can be completed")
    for sid in db.scalars(
        select(SessionRoster.student_id).where(SessionRoster.session_id == s.id)
    ):
        safe_insert(
            db,
            AttendanceRecord,
            dict(
                id=uid(),
                created_at=now(),
                session_id=s.id,
                student_id=sid,
                status="ABSENT",
                source="FINALIZATION",
                recorded_at=now(),
                updated_at=now(),
            ),
            ["session_id", "student_id"],
        )
    s.status = "COMPLETED"
    s.closed_at = now()
    audit(db, user, "SESSION_COMPLETED", s.id)
    db.flush()
    return s


def totals(db, s, student_id=None):
    q = select(AttendanceRecord.status, func.count()).where(
        AttendanceRecord.session_id == s.id
    )
    roster = (
        select(func.count())
        .select_from(SessionRoster)
        .where(SessionRoster.session_id == s.id)
    )
    if student_id:
        q = q.where(AttendanceRecord.student_id == student_id)
        roster = roster.where(SessionRoster.student_id == student_id)
    counts = dict(db.execute(q.group_by(AttendanceRecord.status)).all())
    enrolled = db.scalar(roster) or 0
    if s.status == "SCHEDULED":
        enq = (
            select(func.count())
            .select_from(CourseEnrollment)
            .where(CourseEnrollment.course_id == s.course_id)
        )
        if student_id:
            enq = enq.where(CourseEnrollment.student_id == student_id)
        enrolled = db.scalar(enq) or 0
    p = s.policy or policy(db)
    denominator = enrolled - (
        0 if p["excused_in_denominator"] else counts.get("EXCUSED", 0)
    )
    present = counts.get("PRESENT", 0) + (
        counts.get("LATE", 0) if p["late_counts_present"] else 0
    )
    return {
        "roster_count": enrolled,
        "present": counts.get("PRESENT", 0),
        "late": counts.get("LATE", 0),
        "absent": counts.get("ABSENT", 0),
        "excused": counts.get("EXCUSED", 0),
        "review": counts.get("REVIEW", 0),
        "pending": max(0, enrolled - sum(counts.values())),
        "attendance_percentage": (
            round(100 * present / denominator, 2) if denominator else 0
        ),
        "denominator": denominator,
        "credited": present,
    }
