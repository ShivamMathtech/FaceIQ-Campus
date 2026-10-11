import time, uuid
from collections import Counter
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy import select, func
from app.db.database import get_db
from app.core.security import staff, current_user, admin, limiter
from app.models.entities import *
from app.schemas.contracts import SessionCreate, Correction, Manual
from app.services.common import *
from app.services.biometrics import template_vector
from app.computer_vision.engine import (
    engine,
    decode_image,
    match_embedding,
    MODEL_VERSION,
)
from app.attendance.service import verify_attendance, finalize, totals, event
from app.api.academic import page

router = APIRouter(prefix="/api", tags=["Sessions and attendance"])


def session_view(db, s):
    c = require(db, Course, s.course_id)
    f = require(db, User, s.faculty_id)
    return {
        **columns(s),
        "course_name": c.name,
        "course_code": c.code,
        "section": c.section,
        "faculty_name": f.name,
    }


@router.get("/sessions")
def sessions(
    course_id: str = "",
    status: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(current_user),
    db=Depends(get_db),
):
    q = select(AttendanceSession).where(
        AttendanceSession.course_id.in_(visible_courses(db, user))
    )
    if course_id:
        q = q.where(AttendanceSession.course_id == course_id)
    if status:
        q = q.where(AttendanceSession.status == status)
    return page(
        db,
        q.order_by(AttendanceSession.starts_at.desc()),
        lambda s: session_view(db, s),
        offset,
        limit,
    )


def validate_schedule(db, body, exclude=None):
    c = db.scalar(select(Course).where(Course.id == body.course_id).with_for_update())
    if not c or not c.active:
        raise HTTPException(422, "Choose an active course")
    u = require(db, User, body.faculty_id)
    if (
        not u.active
        or u.role != "faculty"
        or not db.scalar(
            select(FacultyCourseAssignment.id).where(
                FacultyCourseAssignment.course_id == c.id,
                FacultyCourseAssignment.faculty_id == u.id,
            )
        )
    ):
        raise HTTPException(422, "Faculty must be actively assigned to the course")
    q = select(AttendanceSession.id).where(
        AttendanceSession.course_id == c.id,
        AttendanceSession.status != "CANCELLED",
        AttendanceSession.starts_at < body.ends_at,
        AttendanceSession.ends_at > body.starts_at,
    )
    if exclude:
        q = q.where(AttendanceSession.id != exclude)
    if db.scalar(q):
        raise HTTPException(
            409, "Overlapping session exists for this course and section"
        )


@router.post("/sessions", status_code=201)
def schedule(body: SessionCreate, user=Depends(admin), db=Depends(get_db)):
    validate_schedule(db, body)
    s = AttendanceSession(**body.model_dump())
    db.add(s)
    db.flush()
    audit(db, user, "SESSION_SCHEDULED", s.id)
    return session_view(db, s)


@router.patch("/sessions/{sid}")
def reschedule(sid: str, body: SessionCreate, user=Depends(admin), db=Depends(get_db)):
    s = lock_session(db, sid)
    if not s:
        raise HTTPException(404, "Session not found")
    if s.status != "SCHEDULED":
        raise HTTPException(409, "Only scheduled sessions can be edited")
    validate_schedule(db, body, sid)
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    audit(db, user, "SESSION_RESCHEDULED", sid)
    return session_view(db, s)


@router.post("/sessions/{sid}/cancel")
def cancel(sid: str, user=Depends(admin), db=Depends(get_db)):
    s = lock_session(db, sid)
    if not s:
        raise HTTPException(404, "Session not found")
    if s.status != "SCHEDULED":
        raise HTTPException(409, "Only scheduled sessions can be cancelled")
    s.status = "CANCELLED"
    audit(db, user, "SESSION_CANCELLED", sid)
    return session_view(db, s)


@router.post("/sessions/{sid}/start")
def start(sid: str, user=Depends(staff), db=Depends(get_db)):
    s = session_scope(db, user, sid, True)
    db.scalar(select(Course).where(Course.id == s.course_id).with_for_update())
    s = lock_session(db, sid)
    if s.status == "ACTIVE":
        return session_view(db, s)
    if s.status != "SCHEDULED":
        raise HTTPException(409, "Session cannot be started")
    if now() < s.starts_at - timedelta(minutes=15) or now() >= s.ends_at:
        raise HTTPException(
            409,
            "Start is allowed from 15 minutes before the scheduled start until the scheduled end",
        )
    c = require(db, Course, s.course_id)
    f = require(db, User, s.faculty_id)
    if not c.active or not f.active:
        raise HTTPException(409, "Course or assigned faculty is inactive")
    if db.scalar(
        select(AttendanceSession.id).where(
            AttendanceSession.course_id == s.course_id,
            AttendanceSession.status == "ACTIVE",
        )
    ):
        raise HTTPException(409, "Course already has an active session")
    s.status = "ACTIVE"
    s.opened_at = now()
    s.policy = policy(db)
    for st in db.scalars(
        select(Student)
        .join(CourseEnrollment)
        .where(
            CourseEnrollment.course_id == c.id,
            Student.active == True,
            Student.section == c.section,
            Student.semester == c.semester,
            Student.department == c.department,
        )
    ):
        db.add(SessionRoster(session_id=s.id, student_id=st.id))
    audit(db, user, "SESSION_STARTED", sid)
    db.flush()
    return session_view(db, s)


@router.post("/sessions/{sid}/end")
def end(sid: str, user=Depends(staff), db=Depends(get_db)):
    s = session_scope(db, user, sid, True)
    finalize(db, s, user)
    return session_view(db, s)


@router.get("/sessions/{sid}/summary")
def summary(sid: str, user=Depends(current_user), db=Depends(get_db)):
    s = session_scope(db, user, sid)
    personal = own_student(db, user).id if user.role == "student" else None
    duplicate = (
        db.scalar(
            select(func.count())
            .select_from(RecognitionEvent)
            .where(
                RecognitionEvent.session_id == sid,
                RecognitionEvent.status == "ALREADY_PRESENT",
            )
        )
        if not personal
        else None
    )
    return {
        **session_view(db, s),
        **totals(db, s, personal),
        "duplicate_events": duplicate,
        "recognition": engine.status(),
    }


def attendance_rows(db, s, user, search="", status=""):
    q = (
        select(AttendanceRecord, Student)
        .join(Student)
        .where(AttendanceRecord.session_id == s.id)
    )
    if user.role == "student":
        q = q.where(Student.user_id == user.id)
    if search:
        q = q.where(
            (Student.erp_id.ilike("%" + search + "%"))
            | (Student.name.ilike("%" + search + "%"))
        )
    if status:
        q = q.where(AttendanceRecord.status == status)
    return q


@router.get("/sessions/{sid}/attendance")
def attendance(
    sid: str,
    search: str = "",
    status: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(current_user),
    db=Depends(get_db),
):
    s = session_scope(db, user, sid)
    q = attendance_rows(db, s, user, search, status)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    items = [
        {**columns(r), "name": st.name, "erp_id": st.erp_id}
        for r, st in db.execute(q.order_by(Student.name).offset(offset).limit(limit))
    ]
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/sessions/{sid}/roster")
def roster(
    sid: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(staff),
    db=Depends(get_db),
):
    session_scope(db, user, sid)
    q = (
        select(Student)
        .join(SessionRoster)
        .where(SessionRoster.session_id == sid)
        .order_by(Student.name)
    )

    def view(st):
        rec = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id == sid, AttendanceRecord.student_id == st.id
            )
        )
        return {
            "student_id": st.id,
            "name": st.name,
            "erp_id": st.erp_id,
            "attendance_id": rec.id if rec else None,
            "status": rec.status if rec else "PENDING",
        }

    return page(db, q, view, offset, limit)


@router.get("/sessions/{sid}/recognition-events")
def events(
    sid: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(staff),
    db=Depends(get_db),
):
    session_scope(db, user, sid)
    q = (
        select(RecognitionEvent)
        .where(RecognitionEvent.session_id == sid)
        .order_by(RecognitionEvent.created_at.desc())
    )

    def view(e):
        st = db.get(Student, e.student_id) if e.student_id else None
        return {
            **columns(e),
            "name": st.name if st else None,
            "erp_id": st.erp_id if st else None,
        }

    return page(db, q, view, offset, limit)


@router.post("/sessions/{sid}/recognition-events")
def recognize(
    sid: str,
    frame: UploadFile = File(...),
    request_id: str = Form(...),
    user=Depends(staff),
    db=Depends(get_db),
):
    limiter.check(("recognition", user.id), 90)
    try:
        uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(422, "request_id must be a UUID")
    s = session_scope(db, user, sid, True)
    s = lock_session(db, sid)
    if s.status != "ACTIVE" or now() > s.ends_at:
        raise HTTPException(409, "Attendance window is closed")
    prior = list(
        db.scalars(
            select(RecognitionEvent).where(
                RecognitionEvent.session_id == sid,
                RecognitionEvent.request_id.like(request_id + ":%"),
            )
        )
    )
    if prior:
        return {
            "results": [columns(e) for e in prior],
            "replayed": True,
            "latency_ms": 0,
        }
    if not engine.available:
        raise HTTPException(503, "Recognition setup required: " + engine.message)
    data = frame.file.read(5 * 1024 * 1024 + 1)
    frame.file.close()
    image, _ = decode_image(data)
    begin = time.perf_counter()
    detections = engine.analyze(image)
    c = require(db, Course, s.course_id)
    candidates = []
    from datetime import timedelta

    expiry = now() - timedelta(days=s.policy["biometric_retention_days"])
    q = (
        select(BiometricTemplate)
        .join(Student)
        .join(SessionRoster, SessionRoster.student_id == Student.id)
        .join(CourseEnrollment, CourseEnrollment.student_id == Student.id)
        .where(
            SessionRoster.session_id == sid,
            CourseEnrollment.course_id == s.course_id,
            Student.active == True,
            Student.consent == True,
            Student.section == c.section,
            Student.semester == c.semester,
            Student.department == c.department,
            BiometricTemplate.active == True,
            BiometricTemplate.model == MODEL_VERSION,
            BiometricTemplate.created_at >= expiry,
        )
        .order_by(Student.id)
        .with_for_update(of=Student)
    )
    for t in db.scalars(q):
        if t.encrypted_embedding:
            candidates.append((t.student_id, template_vector(t)))
    prepared = []
    for d in detections:
        status, student_id, score = (
            ("REVIEW_REQUIRED", None, None)
            if d["quality_error"]
            else match_embedding(
                d["embedding"],
                candidates,
                s.policy["recognition_threshold"],
                s.policy["ambiguity_margin"],
            )
        )
        prepared.append((d, status, student_id, score))
    identities = Counter(x[2] for x in prepared if x[2])
    engine.retain_session_tracks(
        sid,
        {
            sid
            for _, status, sid, _ in prepared
            if status == "MATCH" and identities[sid] == 1
        },
    )
    results = []
    for i, (d, status, student_id, score) in enumerate(prepared):
        if status == "MATCH":
            if identities[student_id] > 1:
                status = "REVIEW_REQUIRED"
            elif s.policy["liveness_required"] or not s.policy["calibration_approved"]:
                status = "REVIEW_REQUIRED"
            elif not engine.smooth(
                sid, student_id, d["box"], s.policy["smoothing_frames"]
            ):
                status = "PROCESSING"
        e = (
            verify_attendance(db, sid, student_id, request_id + ":" + str(i), score)
            if status == "MATCH"
            else event(db, sid, request_id + ":" + str(i), status, student_id, score)
        )
        st = db.get(Student, e.student_id) if e.student_id else None
        results.append(
            {
                **columns(e),
                "name": st.name if st else None,
                "erp_id": st.erp_id if st else None,
                "box": d["box"],
                "quality_error": d["quality_error"],
            }
        )
    if not results:
        results = [columns(event(db, sid, request_id + ":0", "NO_FACE"))]
    return {
        "results": results,
        "latency_ms": round((time.perf_counter() - begin) * 1000, 1),
        "frame_width": image.shape[1],
        "frame_height": image.shape[0],
        "replayed": False,
        "summary": totals(db, s),
    }


def correction_allowed(db, user, s):
    if user.role == "faculty" and not policy(db)["faculty_corrections"]:
        raise HTTPException(
            403, "Faculty corrections are disabled; contact an administrator"
        )
    if s.status not in ("ACTIVE", "COMPLETED"):
        raise HTTPException(409, "Session must be active or completed")


@router.post("/sessions/{sid}/manual-attendance")
def manual(sid: str, body: Manual, user=Depends(staff), db=Depends(get_db)):
    s = session_scope(db, user, sid, True)
    s = lock_session(db, sid)
    correction_allowed(db, user, s)
    if not db.scalar(
        select(SessionRoster.id).where(
            SessionRoster.session_id == sid, SessionRoster.student_id == body.student_id
        )
    ):
        raise HTTPException(422, "Student is not in this session roster")
    r = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == sid,
            AttendanceRecord.student_id == body.student_id,
        )
    )
    old = columns(r) if r else None
    if not r:
        r = AttendanceRecord(
            session_id=sid,
            student_id=body.student_id,
            status=body.status,
            source="MANUAL",
        )
        db.add(r)
    else:
        r.status = body.status
        r.source = "MANUAL"
    db.flush()
    audit(
        db,
        user,
        "ATTENDANCE_CORRECTED",
        r.id,
        {
            "before": (
                {"status": old["status"], "source": old["source"]} if old else None
            ),
            "after": {"status": r.status, "source": r.source},
            "reason": body.reason,
            "session_id": sid,
        },
    )
    return columns(r)


@router.patch("/attendance/{aid}")
def correct(aid: str, body: Correction, user=Depends(staff), db=Depends(get_db)):
    r = require(db, AttendanceRecord, aid)
    return manual(
        r.session_id, Manual(student_id=r.student_id, **body.model_dump()), user, db
    )
