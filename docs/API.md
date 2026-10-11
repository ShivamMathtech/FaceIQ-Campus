# API examples and endpoint inventory

Open `http://127.0.0.1:8000/docs` for complete request schemas and validation rules. All timestamps returned by the database are UTC; schedule input must include a timezone offset. The frontend normalizes server timestamps and displays local browser time. List responses use `{items,total,offset,limit}` with a maximum page size of 100. Attendance exports are capped at 10,000 filtered rows.

## Authentication

```http
POST /api/auth/login
Content-Type: application/json

{"email":"YOUR_ADMIN_EMAIL","password":"YOUR_CHOSEN_PASSWORD"}
```

Use the returned opaque `access_token` in `Authorization: Bearer TOKEN` for subsequent API calls. Never put it in a URL. POST `/api/auth/logout` revokes the current token. GET `/api/auth/me` returns only safe account fields.

## Academic setup

```http
POST /api/students
Authorization: Bearer TOKEN
Content-Type: application/json

{"name":"Fictional Example","erp_id":"EXAMPLE001","email":"","department":"Computer Science","program":"B.Tech","semester":4,"section":"A","active":true,"consent":false}
```

```http
POST /api/courses
Authorization: Bearer TOKEN
Content-Type: application/json

{"code":"CS301","name":"Data Structures","department":"Computer Science","semester":4,"section":"A","academic_year":"2026-2027","active":true}
```

Create faculty through POST `/api/faculty` with `{name,email,password}`. POST `/api/faculty/assignments` with `{course_id,faculty_id}` and POST `/api/courses/{id}/enrollments` with `{student_ids:[...]}`. Enrollment identities must match department, semester and section.

Schedule with POST `/api/sessions`:

```json
{"course_id":"RETURNED_COURSE_ID","faculty_id":"RETURNED_FACULTY_ID","starts_at":"2026-10-11T09:00:00+05:30","ends_at":"2026-10-11T10:00:00+05:30","room":"Lab 3"}
```

Use appropriate current scheduling values; this example date is illustrative.

## Recognition

POST `/api/sessions/{id}/recognition-events` is **multipart form data**, not a JSON identity assertion. It accepts:

- `frame`: actual JPEG/PNG frame.
- `request_id`: UUID generated once for that request; reuse it only when retrying the same frame request.

The response contains `results`, detector-space `box` coordinates, model cosine `score`, `status`, `latency_ms`, frame dimensions and summary. Status codes include PROCESSING, PRESENT_RECORDED, ALREADY_PRESENT, UNKNOWN_FACE, LOW_CONFIDENCE, MULTIPLE_CANDIDATES, REVIEW_REQUIRED and NO_FACE. Non-enrolled identities are never searched globally; such faces are normally UNKNOWN_FACE rather than a revealed outside identity. The internal attendance boundary also rejects non-enrolled IDs with NOT_ENROLLED.

Do not interpret a score as confidence probability or a recognition event as an attendance row. A retried processed request can replay the original PRESENT_RECORDED event; it cannot insert a second record.

## Manual attendance / correction

```http
POST /api/sessions/SESSION_ID/manual-attendance
Authorization: Bearer TOKEN
Content-Type: application/json

{"student_id":"ROSTER_STUDENT_ID","status":"PRESENT","reason":"Faculty verified institutional identity in person"}
```

PATCH `/api/attendance/{attendance_id}` accepts `{status,reason}`. Valid states are PRESENT, LATE, ABSENT, EXCUSED and REVIEW. Only the administrator or the assigned faculty with correction permission can make changes. Reasons require at least five characters. Both original and corrected states are audited.

## Main routes

| Module | Routes |
|---|---|
| Auth | POST login/logout; GET me under `/api/auth` |
| Students | GET/POST `/api/students`; GET/PATCH `/api/students/{id}` |
| Photo | POST/GET `/api/students/{id}/photo` |
| Biometric lifecycle | POST `/api/students/{id}/biometric-template/regenerate`; DELETE `/api/students/{id}/biometric-template` |
| Student portal | POST `/api/students/{id}/account`; self-scoped existing read APIs |
| Faculty | GET/POST `/api/faculty`; PATCH `/api/faculty/{id}` |
| Assignment | POST `/api/faculty/assignments`; DELETE `/api/faculty/assignments/{course}/{faculty}` |
| Courses | GET/POST `/api/courses`; PATCH `/api/courses/{id}` |
| Enrollment | GET/POST `/api/courses/{id}/enrollments`; DELETE `/api/courses/{id}/enrollments/{student}` |
| Sessions | GET/POST `/api/sessions`; PATCH `/api/sessions/{id}`; POST start/end/cancel actions |
| Session detail | GET summary/roster/attendance/recognition-events under `/api/sessions/{id}` |
| Recognition | POST `/api/sessions/{id}/recognition-events` with image form data |
| Attendance | POST manual-attendance per session; PATCH `/api/attendance/{id}` |
| Dashboard | GET `/api/dashboard/summary` |
| Analytics | GET `/api/analytics/attendance`; GET `/api/analytics/students` |
| Reports | GET `/api/reports/attendance` with `format=json/csv/xlsx`, course/session/search/status/from_date/to_date filters |
| Audit | GET `/api/audit-logs` with optional action/offset/limit and CSV format |
| Settings | GET/PUT `/api/settings`; POST `/api/settings/retention/run` |
| Health | GET `/api/health` |

The current schema's immutable course identity can be archived and recreated; PATCH changes course display name and activity status. Students may be deactivated without academic-record deletion.

## WebSocket protocol

Connect to `/api/ws/sessions/{session_id}` using an allowed Origin. Within five seconds send:

```json
{"token":"CURRENT_BEARER_TOKEN"}
```

The server sends bounded snapshots about once per second:

```json
{"type":"snapshot","summary":{"status":"ACTIVE","present":0,"pending":20},"events":[]}
```

A camera UI may send `{"type":"camera_health","status":"LIVE"}`; the server echoes its operational health. Student accounts are not authorized for staff live streams. Expired/revoked tokens and loss of resource assignment close the connection. Camera health is a client operational signal, not liveness evidence.

## Errors

401 = invalid/expired login; 403 = role/resource scope failure; 404 = missing resource; 409 = duplicate identity, lifecycle conflict or closed attendance; 413 = body/image too large; 422 = invalid fields/image/academic relationship; 429 = rate limit or busy inference worker; 503 = missing/invalid model or encryption configuration. FastAPI errors use a `detail` string or structured validation list. Database constraint errors return a generic conflict rather than revealing SQL or stored secrets.
