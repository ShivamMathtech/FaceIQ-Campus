import io, csv
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy import select, func, delete
from openpyxl import Workbook
from app.db.database import get_db
from app.core.security import current_user, admin
from app.models.entities import *
from app.schemas.contracts import Policy
from app.services.common import *
from app.services.biometrics import delete_biometrics
from app.api.academic import page
from app.api.sessions import session_view
from app.attendance.service import totals
from app.computer_vision.engine import engine

router = APIRouter(prefix="/api", tags=["Reports and settings"])


def aggregate(db, user):
    q = select(AttendanceSession).where(
        AttendanceSession.course_id.in_(visible_courses(db, user))
    )
    sessions = list(db.scalars(q.order_by(AttendanceSession.starts_at.desc())))
    personal = own_student(db, user).id if user.role == "student" else None
    credited = denominator = present_today = absent_today = 0
    day = {}
    month = {}
    courses = {}
    faculty = {}
    for s in sessions:
        t = totals(db, s, personal)
        date = s.starts_at.date().isoformat()
        if s.starts_at.date() == now().date():
            present_today += t["present"] + t["late"]
            absent_today += t["absent"]
        if s.status != "COMPLETED":
            continue
        credited += t["credited"]
        denominator += t["denominator"]
        c = require(db, Course, s.course_id)
        for target, key, label in [
            (day, date, date),
            (month, date[:7], date[:7]),
            (courses, c.id, c.code + " / " + c.section),
            (faculty, s.faculty_id, require(db, User, s.faculty_id).name),
        ]:
            row = target.setdefault(
                key,
                {
                    "id": key,
                    "name": label,
                    "credited": 0,
                    "denominator": 0,
                    "late": 0,
                    "absent": 0,
                    "sessions": 0,
                },
            )
            row["credited"] += t["credited"]
            row["denominator"] += t["denominator"]
            row["late"] += t["late"]
            row["absent"] += t["absent"]
            row["sessions"] += 1
    for target in (day, month, courses, faculty):
        for v in target.values():
            v["percentage"] = (
                round(100 * v["credited"] / v["denominator"], 2)
                if v["denominator"]
                else 0
            )
    return {
        "overall_percentage": (
            round(100 * credited / denominator, 2) if denominator else 0
        ),
        "completed_denominator": denominator,
        "present_today": present_today,
        "absent_today": absent_today,
        "active_sessions": sum(s.status == "ACTIVE" for s in sessions),
        "recent_sessions": [session_view(db, s) for s in sessions[:5]],
        "daily": sorted(day.values(), key=lambda x: x["name"])[-31:],
        "monthly": sorted(month.values(), key=lambda x: x["name"])[-12:],
        "courses": list(courses.values()),
        "faculty": list(faculty.values()),
    }


@router.get("/dashboard/summary")
def dashboard(user=Depends(current_user), db=Depends(get_db)):
    sq = select(func.count()).select_from(Student)
    if user.role == "faculty":
        sq = sq.where(
            Student.id.in_(
                select(CourseEnrollment.student_id).where(
                    CourseEnrollment.course_id.in_(visible_courses(db, user))
                )
            )
        )
    elif user.role == "student":
        sq = sq.where(Student.user_id == user.id)
    return {
        **aggregate(db, user),
        "student_count": db.scalar(sq),
        "faculty_count": (
            db.scalar(
                select(func.count()).select_from(User).where(User.role == "faculty")
            )
            if user.role == "admin"
            else None
        ),
        "course_count": db.scalar(
            select(func.count()).select_from(visible_courses(db, user).subquery())
        ),
        "recognition": engine.status(),
    }


@router.get("/analytics/attendance")
def analytics(user=Depends(current_user), db=Depends(get_db)):
    return aggregate(db, user)


@router.get("/analytics/students")
def student_analytics(
    search: str = "",
    student_id: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(current_user),
    db=Depends(get_db),
):
    q = select(Student)
    if user.role == "student":
        q = q.where(Student.user_id == user.id)
    elif user.role == "faculty":
        q = q.where(
            Student.id.in_(
                select(CourseEnrollment.student_id).where(
                    CourseEnrollment.course_id.in_(visible_courses(db, user))
                )
            )
        )
    if search:
        q = q.where(
            Student.name.ilike("%" + search + "%")
            | Student.erp_id.ilike("%" + search + "%")
        )
    if student_id:
        q = q.where(Student.id == student_id)

    def view(st):
        counts = {}
        credited = denominator = 0
        rows = db.execute(
            select(AttendanceRecord.status, AttendanceSession.policy)
            .join(
                AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id
            )
            .where(
                AttendanceRecord.student_id == st.id,
                AttendanceSession.status == "COMPLETED",
                AttendanceSession.course_id.in_(visible_courses(db, user)),
            )
        )
        for status, p in rows:
            counts[status] = counts.get(status, 0) + 1
            if status != "EXCUSED" or p["excused_in_denominator"]:
                denominator += 1
            if status == "PRESENT" or (status == "LATE" and p["late_counts_present"]):
                credited += 1
        return {
            "id": st.id,
            "name": st.name,
            "erp_id": st.erp_id,
            "credited": credited,
            "denominator": denominator,
            "percentage": round(100 * credited / denominator, 2) if denominator else 0,
            "late": counts.get("LATE", 0),
            "absent": counts.get("ABSENT", 0),
            "sessions": sum(counts.values()),
        }

    return page(db, q.order_by(Student.name, Student.id), view, offset, limit)


def report_query(db, user, course_id, session_id, search, status, from_date, to_date):
    q = (
        select(AttendanceRecord, Student, AttendanceSession, Course)
        .join(Student, Student.id == AttendanceRecord.student_id)
        .join(AttendanceSession, AttendanceSession.id == AttendanceRecord.session_id)
        .join(Course, Course.id == AttendanceSession.course_id)
        .where(Course.id.in_(visible_courses(db, user)))
    )
    if user.role == "student":
        q = q.where(Student.user_id == user.id)
    if course_id:
        q = q.where(Course.id == course_id)
    if session_id:
        q = q.where(AttendanceSession.id == session_id)
    if search:
        q = q.where(
            Student.name.ilike("%" + search + "%")
            | Student.erp_id.ilike("%" + search + "%")
        )
    if status:
        q = q.where(AttendanceRecord.status == status)
    try:
        if from_date:
            q = q.where(
                AttendanceSession.starts_at >= datetime.fromisoformat(from_date)
            )
        if to_date:
            q = q.where(
                AttendanceSession.starts_at
                < datetime.fromisoformat(to_date) + timedelta(days=1)
            )
    except ValueError:
        raise HTTPException(422, "Dates must use YYYY-MM-DD")
    return q.order_by(AttendanceSession.starts_at.desc(), Student.name)


def report_row(r, st, s, c):
    return {
        "id": r.id,
        "session_id": s.id,
        "course": c.code,
        "section": c.section,
        "date": s.starts_at.date().isoformat(),
        "name": st.name,
        "erp_id": st.erp_id,
        "status": r.status,
        "source": r.source,
        "recorded_at": r.recorded_at.isoformat() + "Z",
    }


def spreadsheet_safe(v):
    text = str(v if v is not None else "")
    return (
        "'" + text
        if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
        else text
    )


def export_rows(rows, format, filename):
    headers = list(rows[0]) if rows else ["No records"]
    if format == "csv":
        buffer = io.StringIO()
        w = csv.writer(buffer)
        w.writerow(headers)
        for row in rows:
            w.writerow([spreadsheet_safe(row[k]) for k in headers])
        data = ("\ufeff" + buffer.getvalue()).encode()
        media = "text/csv"
    elif format == "xlsx":
        wb = Workbook(write_only=True)
        ws = wb.create_sheet("Attendance")
        ws.append(headers)
        for row in rows:
            ws.append([spreadsheet_safe(row[k]) for k in headers])
        buffer = io.BytesIO()
        wb.save(buffer)
        data = buffer.getvalue()
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        raise HTTPException(422, "Choose csv, xlsx or json")
    return Response(
        data,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.{format}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/reports/attendance")
def report(
    course_id: str = "",
    session_id: str = "",
    search: str = "",
    status: str = "",
    from_date: str = "",
    to_date: str = "",
    format: str = "json",
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(current_user),
    db=Depends(get_db),
):
    q = report_query(
        db, user, course_id, session_id, search, status, from_date, to_date
    )
    total = db.scalar(select(func.count()).select_from(q.order_by(None).subquery()))
    if format != "json":
        if total > 10000:
            raise HTTPException(422, "Narrow filters to at most 10,000 export rows")
        rows = [report_row(*row) for row in db.execute(q)]
        audit(
            db,
            user,
            "ATTENDANCE_EXPORTED",
            session_id or course_id or "filtered",
            {"rows": total, "format": format},
        )
        return export_rows(rows, format, "faceiq-attendance")
    return {
        "items": [
            report_row(*row) for row in db.execute(q.offset(offset).limit(limit))
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/audit-logs")
def audits(
    action: str = "",
    format: str = "json",
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(admin),
    db=Depends(get_db),
):
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action.ilike("%" + action + "%"))
    q = q.order_by(AuditLog.created_at.desc())
    if format == "csv":
        import json

        rows = [
            {
                **columns(a),
                "details": json.dumps(a.details),
                "created_at": a.created_at.isoformat() + "Z",
            }
            for a in db.scalars(q.limit(10000))
        ]
        audit(db, user, "AUDIT_EXPORTED", "audit", {"rows": len(rows)})
        return export_rows(rows, "csv", "faceiq-audit")
    return page(db, q, columns, offset, limit)


@router.get("/settings")
def settings(user=Depends(current_user), db=Depends(get_db)):
    return {"policy": policy(db), "recognition": engine.status()}


@router.put("/settings")
def change_settings(body: Policy, user=Depends(admin), db=Depends(get_db)):
    if body.calibration_approved and len(body.calibration_note.strip()) < 10:
        raise HTTPException(
            422,
            "Document representative calibration evidence before enabling auto-attendance",
        )
    prior = policy(db)
    row = db.get(ApplicationSetting, "attendance_policy")
    if not row:
        row = ApplicationSetting(key="attendance_policy", value=body.model_dump())
        db.add(row)
    else:
        row.value = body.model_dump()
    audit(
        db,
        user,
        "POLICY_UPDATED",
        "attendance_policy",
        {"before": prior, "after": body.model_dump()},
    )
    return {
        "policy": body.model_dump(),
        "note": "New policy applies to new sessions; correction permission is live",
    }


@router.post("/settings/retention/run")
def retention(user=Depends(admin), db=Depends(get_db)):
    p = policy(db)
    cutoff = now() - timedelta(days=p["event_retention_days"])
    count = db.execute(
        delete(RecognitionEvent).where(RecognitionEvent.created_at < cutoff)
    ).rowcount
    db.execute(delete(AuthSession).where(AuthSession.expires_at < now()))
    bio_cutoff = now() - timedelta(days=p["biometric_retention_days"])
    removed = 0
    for s in db.scalars(select(Student).where(Student.photo.is_not(None))):
        latest = db.scalar(
            select(func.max(BiometricTemplate.created_at)).where(
                BiometricTemplate.student_id == s.id, BiometricTemplate.active == True
            )
        )
        if (
            not s.consent
            or not s.active
            or (latest or s.photo_updated_at or s.created_at) < bio_cutoff
        ):
            delete_biometrics(db, s, user, "RETENTION_EXPIRED")
            removed += 1
    audit(
        db,
        user,
        "RETENTION_APPLIED",
        "settings",
        {"events_deleted": count, "biometrics_deleted": removed},
    )
    return {"events_deleted": count, "biometrics_deleted": removed}
