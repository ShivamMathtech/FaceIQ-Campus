from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Response
from sqlalchemy import select, func, or_, delete
from app.db.database import get_db
from app.core.security import admin, staff, current_user, hash_password, cipher, limiter
from app.models.entities import *
from app.schemas.contracts import *
from app.services.common import *
from app.services.biometrics import delete_biometrics, register_photo

router = APIRouter(prefix="/api", tags=["Academic management"])


def student_for_update(db, sid):
    student = db.scalar(
        select(Student)
        .where(Student.id == sid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not student:
        raise HTTPException(404, "Student not found")
    return student


def student_scope(db, user, sid):
    s = require(db, Student, sid)
    if user.role == "admin":
        return s
    if user.role == "student" and s.user_id == user.id:
        return s
    if user.role == "faculty" and db.scalar(
        select(CourseEnrollment.id).where(
            CourseEnrollment.student_id == sid,
            CourseEnrollment.course_id.in_(visible_courses(db, user)),
        )
    ):
        return s
    raise HTTPException(403, "Not authorized for this student")


def page(db, q, serializer, offset, limit):
    total = db.scalar(select(func.count()).select_from(q.order_by(None).subquery()))
    return {
        "items": [serializer(x) for x in db.scalars(q.offset(offset).limit(limit))],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/students")
def students(
    search: str = "",
    department: str = "",
    active: bool | None = None,
    sort: str = "name",
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
            or_(
                Student.name.ilike("%" + search + "%"),
                Student.erp_id.ilike("%" + search + "%"),
            )
        )
    if department:
        q = q.where(Student.department == department)
    if active is not None:
        q = q.where(Student.active == active)
    q = q.order_by(Student.erp_id if sort == "erp_id" else Student.name, Student.id)
    return page(db, q, student_view, offset, limit)


@router.post("/students", status_code=201)
def create_student(body: StudentCreate, user=Depends(admin), db=Depends(get_db)):
    data = body.model_dump()
    data["erp_id"] = data["erp_id"].upper()
    s = Student(**data, consent_at=now() if data["consent"] else None)
    db.add(s)
    db.flush()
    audit(
        db,
        user,
        "STUDENT_CREATED",
        s.id,
        {"consent": s.consent, "notice": s.consent_notice},
    )
    return student_view(s)


@router.get("/students/{sid}")
def get_student(sid: str, user=Depends(current_user), db=Depends(get_db)):
    s = student_scope(db, user, sid)
    enrollments = [
        columns(c)
        for c in db.scalars(
            select(Course)
            .join(CourseEnrollment)
            .where(
                CourseEnrollment.student_id == sid,
                Course.id.in_(visible_courses(db, user)),
            )
        )
    ]
    templates = [
        columns(t, ("encrypted_embedding",))
        for t in db.scalars(
            select(BiometricTemplate)
            .where(BiometricTemplate.student_id == sid)
            .order_by(BiometricTemplate.version.desc())
            .limit(20)
        )
    ]
    history = (
        [
            columns(a)
            for a in db.scalars(
                select(AuditLog)
                .where(AuditLog.resource_id == sid)
                .order_by(AuditLog.created_at.desc())
                .limit(30)
            )
        ]
        if user.role in ("admin", "student")
        else []
    )
    return {
        **student_view(s),
        "enrollments": enrollments,
        "templates": templates,
        "history": history,
    }


@router.patch("/students/{sid}")
def edit_student(sid: str, body: StudentPatch, user=Depends(admin), db=Depends(get_db)):
    s = student_for_update(db, sid)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "erp_id" in changes:
        changes["erp_id"] = changes["erp_id"].upper()
    old = {k: getattr(s, k) for k in changes}
    for k, v in changes.items():
        setattr(s, k, v)
    if changes.get("consent") is True and not old.get("consent"):
        s.consent_at = now()
    if changes.get("consent") is False or changes.get("active") is False:
        delete_biometrics(db, s, user, "CONSENT_WITHDRAWN_OR_DEACTIVATED")
    audit(db, user, "STUDENT_UPDATED", sid, {"before": old, "after": changes})
    db.flush()
    return student_view(s)


@router.post("/students/{sid}/photo")
async def upload_photo(
    sid: str, file: UploadFile = File(...), user=Depends(admin), db=Depends(get_db)
):
    limiter.check(("photo", user.id), 20)
    s = student_for_update(db, sid)
    if not s.consent or not s.active:
        raise HTTPException(
            409, "Active enrollment and documented biometric consent are required"
        )
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(422, "Upload JPEG or PNG")
    data = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    # CPU inference is offloaded to avoid blocking the event loop.
    from starlette.concurrency import run_in_threadpool

    await run_in_threadpool(register_photo, db, s, data, user)
    return student_view(s)


@router.get("/students/{sid}/photo")
def photo(sid: str, user=Depends(current_user), db=Depends(get_db)):
    s = student_scope(db, user, sid)
    if not s.photo:
        raise HTTPException(404, "No photograph available")
    return Response(
        cipher().decrypt(s.photo),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/students/{sid}/biometric-template/regenerate")
def regenerate(sid: str, user=Depends(admin), db=Depends(get_db)):
    s = student_for_update(db, sid)
    if not s.active or not s.consent or not s.photo:
        raise HTTPException(
            409, "Active consent and an existing photograph are required"
        )
    from app.computer_vision.engine import engine

    if not engine.available:
        raise HTTPException(503, "Model setup required")
    register_photo(db, s, cipher().decrypt(s.photo), user)
    return student_view(s)


@router.delete("/students/{sid}/biometric-template")
def delete_template(sid: str, user=Depends(admin), db=Depends(get_db)):
    s = student_for_update(db, sid)
    delete_biometrics(db, s, user)
    return {"ok": True}


@router.post("/students/{sid}/account", status_code=201)
def student_account(
    sid: str, body: UserCreate, user=Depends(admin), db=Depends(get_db)
):
    s = require(db, Student, sid)
    if s.user_id:
        raise HTTPException(409, "Student already has an account")
    u = User(
        name=body.name,
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        role="student",
    )
    db.add(u)
    db.flush()
    s.user_id = u.id
    audit(db, user, "STUDENT_ACCOUNT_CREATED", sid)
    return user_view(u)


@router.get("/faculty")
def faculty(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(staff),
    db=Depends(get_db),
):
    q = select(User).where(User.role == "faculty")
    if user.role == "faculty":
        q = q.where(User.id == user.id)

    def view(u):
        return {
            **user_view(u),
            "course_ids": list(
                db.scalars(
                    select(FacultyCourseAssignment.course_id).where(
                        FacultyCourseAssignment.faculty_id == u.id
                    )
                )
            ),
        }

    return page(db, q.order_by(User.name), view, offset, limit)


@router.post("/faculty", status_code=201)
def create_faculty(body: UserCreate, user=Depends(admin), db=Depends(get_db)):
    u = User(
        name=body.name,
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        role="faculty",
    )
    db.add(u)
    db.flush()
    audit(db, user, "FACULTY_CREATED", u.id)
    return user_view(u)


@router.patch("/faculty/{fid}")
def edit_faculty(fid: str, body: UserPatch, user=Depends(admin), db=Depends(get_db)):
    u = require(db, User, fid)
    if u.role != "faculty":
        raise HTTPException(422, "Not a faculty account")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "password" in changes:
        u.password_hash = hash_password(changes.pop("password"))
    for k, v in changes.items():
        setattr(u, k, v)
    audit(db, user, "FACULTY_UPDATED", fid, {"fields": list(body.model_fields_set)})
    if body.active is False or body.password:
        db.execute(delete(AuthSession).where(AuthSession.user_id == fid))
    return user_view(u)


@router.post("/faculty/assignments")
def assign(body: Assignment, user=Depends(admin), db=Depends(get_db)):
    c = require(db, Course, body.course_id)
    u = require(db, User, body.faculty_id)
    if u.role != "faculty" or not u.active:
        raise HTTPException(422, "Choose an active faculty member")
    from app.attendance.service import safe_insert

    safe_insert(
        db,
        FacultyCourseAssignment,
        dict(id=uid(), created_at=now(), course_id=c.id, faculty_id=u.id),
        ["course_id", "faculty_id"],
    )
    audit(db, user, "FACULTY_ASSIGNED", c.id, {"faculty_id": u.id})
    return {"ok": True}


@router.delete("/faculty/assignments/{cid}/{fid}")
def unassign(cid: str, fid: str, user=Depends(admin), db=Depends(get_db)):
    require(db, Course, cid)
    if db.scalar(
        select(AttendanceSession.id).where(
            AttendanceSession.course_id == cid,
            AttendanceSession.faculty_id == fid,
            AttendanceSession.status.in_(["SCHEDULED", "ACTIVE"]),
        )
    ):
        raise HTTPException(
            409, "Cancel or finish this faculty member's sessions first"
        )
    db.execute(
        delete(FacultyCourseAssignment).where(
            FacultyCourseAssignment.course_id == cid,
            FacultyCourseAssignment.faculty_id == fid,
        )
    )
    audit(db, user, "FACULTY_UNASSIGNED", cid, {"faculty_id": fid})
    return {"ok": True}


def course_view(db, c):
    return {
        **columns(c),
        "enrolled_count": db.scalar(
            select(func.count())
            .select_from(CourseEnrollment)
            .where(CourseEnrollment.course_id == c.id)
        ),
        "faculty_ids": list(
            db.scalars(
                select(FacultyCourseAssignment.faculty_id).where(
                    FacultyCourseAssignment.course_id == c.id
                )
            )
        ),
    }


@router.get("/courses")
def courses(
    search: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(current_user),
    db=Depends(get_db),
):
    q = select(Course).where(Course.id.in_(visible_courses(db, user)))
    if search:
        q = q.where(
            or_(
                Course.name.ilike("%" + search + "%"),
                Course.code.ilike("%" + search + "%"),
            )
        )
    return page(
        db,
        q.order_by(Course.code, Course.section),
        lambda c: course_view(db, c),
        offset,
        limit,
    )


@router.post("/courses", status_code=201)
def create_course(body: CourseCreate, user=Depends(admin), db=Depends(get_db)):
    c = Course(**body.model_dump())
    db.add(c)
    db.flush()
    audit(db, user, "COURSE_CREATED", c.id)
    return course_view(db, c)


@router.patch("/courses/{cid}")
def edit_course(cid: str, body: CoursePatch, user=Depends(admin), db=Depends(get_db)):
    c = require(db, Course, cid)
    if body.active is False and db.scalar(
        select(AttendanceSession.id).where(
            AttendanceSession.course_id == cid, AttendanceSession.status == "ACTIVE"
        )
    ):
        raise HTTPException(409, "Complete active sessions before archiving")
    for k, v in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(c, k, v)
    audit(db, user, "COURSE_UPDATED", cid, body.model_dump(exclude_unset=True))
    return course_view(db, c)


@router.get("/courses/{cid}/enrollments")
def enrollments(
    cid: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(current_user),
    db=Depends(get_db),
):
    course_scope(db, user, cid)
    q = select(Student).join(CourseEnrollment).where(CourseEnrollment.course_id == cid)
    if user.role == "student":
        q = q.where(Student.user_id == user.id)
    return page(db, q.order_by(Student.name), student_view, offset, limit)


@router.post("/courses/{cid}/enrollments")
def enroll(cid: str, body: Enrollment, user=Depends(admin), db=Depends(get_db)):
    c = require(db, Course, cid)
    if not c.active:
        raise HTTPException(409, "Course is archived")
    from app.attendance.service import safe_insert

    for sid in body.student_ids:
        s = require(db, Student, sid)
        if (
            not s.active
            or s.section != c.section
            or s.semester != c.semester
            or s.department != c.department
        ):
            raise HTTPException(
                422,
                "Student must be active and match course department, semester and section",
            )
        safe_insert(
            db,
            CourseEnrollment,
            dict(id=uid(), created_at=now(), course_id=cid, student_id=sid),
            ["course_id", "student_id"],
        )
    audit(db, user, "STUDENTS_ENROLLED", cid, {"student_ids": body.student_ids})
    return {"ok": True, "note": "Active session rosters remain unchanged"}


@router.delete("/courses/{cid}/enrollments/{sid}")
def unenroll(cid: str, sid: str, user=Depends(admin), db=Depends(get_db)):
    require(db, Course, cid)
    db.execute(
        delete(CourseEnrollment).where(
            CourseEnrollment.course_id == cid, CourseEnrollment.student_id == sid
        )
    )
    audit(db, user, "STUDENT_UNENROLLED", cid, {"student_id": sid})
    return {"ok": True}
