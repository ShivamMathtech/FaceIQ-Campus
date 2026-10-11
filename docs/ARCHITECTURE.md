# Architecture and database contract

## Boundaries

- `frontend/src/pages`: connected management screens. Shared controls live in `components`; TanStack Query handles remote data. Bearer tokens live only in module memory.
- `frontend/src/hooks/useCamera.ts`: the local camera adapter. Explicit permission, one sampled request in flight, AbortController cancellation, connection errors and track release are handled here. Camera media is never automatically started by route entry.
- `backend/app/api`: authentication, academic management, session operations, reporting and settings endpoints. Role dependencies and per-resource checks are server-enforced.
- `backend/app/attendance/service.py`: the trusted internal recognition-to-register boundary, conflict-safe insert, finalization and policy-based totals.
- `backend/app/computer_vision`: verified YuNet/SFace loading, decoded-image limits, quality checks, alignment/features, cosine matching, top-two ambiguity and bounded temporal/position tracking. No public mock adapter exists.
- `backend/app/services/biometrics.py`: encrypt/decrypt and template lifecycle; photos are canonical metadata-stripped JPEGs inside encrypted database blobs.
- `backend/app/websocket/live.py`: authorized database snapshots and camera-health echoes. First-message token authentication; origin allowlist; fresh authorization on each update; no unbounded outbound event queue.
- `backend/app/db` and `models`: SQLAlchemy 2.x persistence. Versioned schema changes live in Alembic.

## Recognition transaction

The browser sends an actual JPEG frame and a UUID request ID. The API checks staff authorization, the assigned session, active status and the server-side attendance window. Previously processed requests replay persisted events. The verified models detect and align faces, generate embeddings and match only eligible roster/enrollment templates. Poor quality, low confidence, ambiguous candidates, uncalibrated policy or unavailable mandatory liveness produce non-attendance outcomes.

After enough consistent samples, the internal attendance service rechecks session and student eligibility and performs an `INSERT ... ON CONFLICT DO NOTHING` against `(session_id, student_id)`. An existing PRESENT/LATE row yields ALREADY_PRESENT; an existing manual ABSENT/EXCUSED/REVIEW is never silently overwritten and requires review. The separate recognition-event row is written in the same transaction. A failed transaction rolls back both effects.

CPU inference runs outside the async event loop. Models are reused, OpenCV CPU threads are bounded, and inference lock acquisition is nonblocking. In SQLite a database request uses an immediate transaction; this prioritizes simple, deterministic consistency over throughput. PostgreSQL uses row-level locks. Keep a single API worker because tracking and rate limits are process-local.

## Entities

| Table | Purpose / relationships | Key constraints |
|---|---|---|
| users | Admin, faculty and optional student accounts | Unique lowercase email; role CHECK; active flag |
| auth_sessions | Opaque token hashes, user and expiry | Unique SHA-256 token hash |
| students | ERP identity, academic fields, consent, encrypted photo | Unique ERP; optional unique user link |
| biometric_templates | Student, model identifier, version, encrypted payload | Unique student/version; old payload erased |
| courses | Code, section, academic year, department and semester | Unique code/section/year |
| course_enrollments | Student ↔ course | Unique course/student |
| faculty_course_assignments | Faculty user ↔ course | Unique course/faculty |
| attendance_sessions | Course, faculty, schedule, state, timestamps, policy snapshot | Valid state; end after start |
| session_rosters | Snapshot at session opening | Unique session/student |
| attendance_records | Student attendance for a session | **Unique session/student**; valid attendance status |
| recognition_events | Detection/matching outcomes separate from attendance | Unique session/request ID; student nullable |
| audit_logs | Actor, action, resource, original/new values and reasons | No API mutation/deletion route |
| application_settings | Validated attendance/retention policy | Unique key |

Course, student, session, ERP, timestamps, status and relationship columns have indexes where queried. Foreign keys are enabled in SQLite and no academic relationship uses destructive cascade deletion. A separate Role, FacultyProfile, Department, Program or Section catalog was intentionally consolidated into constrained User roles and academic text fields for the first deployment.

## State and policy semantics

SCHEDULED → ACTIVE → COMPLETED, or SCHEDULED → CANCELLED. An active session is not cancellable because attendance may already exist. Starting is allowed at most 15 minutes before the schedule; recognition stops at the scheduled end even if finalization has not occurred. Closing is explicit, idempotent and serialized against marking.

Rosters and policy values are snapshotted on start. Enrollment additions affect future sessions; removal immediately prevents further automatic matching while preserving the historical roster. Consent withdrawal or account deactivation does not erase academic history. Late status uses server UTC time against scheduled start + grace, not the browser clock or the instant faculty clicked Start.

Attendance percentages are sums of per-session credited unique records divided by eligible roster counts under each session's policy. Completed-session analytics include finalized absences. Active sessions display pending; no automatic absent record is created before finalization. EXCUSED is excluded from the denominator by default; LATE counts as present by default. Manual review stays uncredited unless corrected.

No sensitive template is exposed by serialization: student and user APIs use explicit safe views, and templates are returned only as version/model/status metadata. Frames are not persisted. Recognition-event count reflects only retained events; retention may reduce historical duplicate-event counts without changing attendance totals.

## Extension points

Future camera providers should submit authorized frames through the same session pipeline. A liveness module must return an explicit verified outcome and fail closed before attendance insertion. Distributed operation requires shared tracking/limiting state and a push broker, rather than increasing Uvicorn workers on the existing process-local implementation. Large deployments should add historical analytics rollups, searchable remote selectors, federation/SSO and independent security review.
