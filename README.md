# FaceIQ Campus

A working academic attendance application with an integrated React UI, FastAPI API, SQLite/PostgreSQL persistence, encrypted face templates, course rosters, faculty authorization, session finalization, reports and an audit trail.

This is a production-oriented reference implementation for a **single campus deployment / single API worker**. It is not a claim of production certification or validated recognition accuracy. See [verification results](docs/TEST-RESULTS.md) and [limitations](#known-limitations).

## Start on Windows 10/11

Install **Python 3.12 x64** with the `py` launcher and **Node.js 22 LTS or newer**. Extract this project to a normal writable directory, such as `C:\Projects\FaceIQ-Campus`. Avoid placing it in Program Files or a synchronized folder that locks the SQLite database.

Open Command Prompt in the extracted project directory:

```bat
install.bat
.venv\Scripts\python.exe scripts\create_admin.py
run_all.bat
```

In PowerShell, use explicit relative command paths:

```powershell
.\install.bat
.\.venv\Scripts\python.exe scripts\create_admin.py
.\run_all.bat
```

`install.bat` creates a virtual environment, installs Python packages, generates a random encryption key if missing, applies Alembic migrations, installs the locked frontend dependencies and builds the frontend. It preserves existing configuration and database contents. The administrator command interactively asks for name, email and a password of at least 12 characters. **There are no default admin credentials.**

| Service | Local URL |
|---|---|
| Application | http://127.0.0.1:5173 |
| OpenAPI / Swagger | http://127.0.0.1:8000/docs |
| API health / model status | http://127.0.0.1:8000/api/health |
| OpenAPI JSON | http://127.0.0.1:8000/openapi.json |

Use `run_backend.bat` and `run_frontend.bat` to start the services separately. Launch scripts check their ports and refuse to kill existing processes. Logs appear in the corresponding console windows. Press Ctrl+C in each console for shutdown. Finalize active sessions through the UI first.

### First-run workflow without face models

1. Sign in as your newly created administrator.
2. Create faculty accounts and courses. Academic department, semester and section must match for enrollment.
3. Register students using verified institutional ERP identities. Biometric consent is optional because manual attendance is supported. Do not record consent without the institutional process.
4. From Courses → Manage, enroll students and assign faculty.
5. Schedule a session with that faculty member. A session can be opened from 15 minutes before its scheduled start until its scheduled end.
6. Open the session and start it. The roster is snapshotted at this point. New enrollments do not silently alter an active register.
7. Use **Review / correct** for a manual attendance alternative. Administrators can do this by default; faculty require the explicit settings permission. Enter a reason.
8. End and finalize. Missing roster records become ABSENT, exactly once. Review reports and download CSV/XLSX.

No mock-recognition switch or identity-submission endpoint is available to the normal application. Missing models never fabricate recognition results. Test-only embeddings are injected by pytest fixtures into a temporary database.

### Optional fictional demo data

```bat
.venv\Scripts\python.exe scripts\seed_demo.py
```

The command asks you to choose a password and creates `faculty.demo@example.test`, six explicitly fictional students, one course, one assignment and a session beginning at command execution time. It creates **no photographs, templates or attendance records**. The fictional faculty account uses your chosen password. Create an administrator separately. Re-running the seed preserves an existing demo course. If its session has expired, schedule another session in the UI.

### Hardware planning baseline

Use a modern four-core x64 CPU, 8 GB RAM (16 GB preferred), about 2 GB free disk for tooling/dependencies, and a 720p webcam. Start at 640-pixel capture width and an 800 ms inference interval. No CUDA or GPU is required. These are deployment planning recommendations, not a validated minimum or a performance guarantee for a specific laptop.

## Real CPU face recognition

The source archive does not bundle the roughly 39 MB of model binaries. Acquire verified models from the official OpenCV Zoo repository:

```bat
.venv\Scripts\python.exe scripts\download_or_configure_model.py
```

The installer downloads an immutable upstream revision and verifies the exact file size and SHA-256 from `model-manifest.json`. Do not substitute arbitrary ONNX downloads. Restart the backend after installation.

| Component | Pinned model | License |
|---|---|---|
| Detector | YuNet `face_detection_yunet_2023mar.onnx` | MIT |
| Embedding network | SFace `face_recognition_sface_2021dec.onnx` | Apache-2.0 |

Upstream: https://github.com/opencv/opencv_zoo . License copies and attribution are under `docs/licenses`. The model revision and official download paths are in `model-manifest.json` and the installer. The older named YuNet model is intentionally paired with OpenCV 4.11's `FaceDetectorYN` API. These permissive software/model licenses do not establish an institution's permission to process student biometric data.

After model setup:

1. Document consent, upload a JPG/PNG photo (maximum 5 MiB, at least 160×160, at most 12 MP), and require exactly one clear face. The server checks actual image content, strips metadata, checks face size, blur and brightness, and creates an encrypted 128-dimensional template.
2. A photo uploaded without models is saved with `SETUP_REQUIRED`, not a successful face registration. Once models are available, regenerate its template from the profile or upload a new photo.
3. Evaluate the threshold and ambiguity margin on consented, representative, held-out data. Settings default to **automatic marking disabled** (`calibration_approved=false`). Add an actual evaluation reference and approve the threshold before starting a new automatic-attendance session.
4. Start a session, choose Enable camera, and grant the browser's camera permission. The camera indication remains visible. Recognition uses only active, consented, unexpired templates in that course's roster and current enrollment/section.
5. Matching requires the configured number of temporally and spatially consistent samples. Similar top candidates and poor-quality detections go to review. The cosine score is not a probability.

The detector sees at most ten faces per sampled frame. Only one inference request is in flight per camera UI. The model is loaded once per API process, inference is bounded by a nonblocking worker lock, capture width and sampling interval are adjustable, and tracks are bounded. The default sample interval is 800 ms, intentionally much slower than video playback. Frames containing only already-present matches trigger a 2.5-second frontend cooldown to reduce repeated inference.

**Liveness is unavailable.** The application does not claim to resist photos, phones or prerecorded video. Enabling mandatory liveness prevents automatic attendance and requires manual review. This is a fail-closed integration point for a future licensed, validated anti-spoofing module.

## Database and consistency

Normal setup:

```bat
.venv\Scripts\python.exe scripts\initialize_database.py
```

This runs `alembic upgrade head`; it does not reset tables. The default database is `storage/faceiq.db`. SQLite uses foreign keys, WAL and `BEGIN IMMEDIATE` to serialize competing writers. PostgreSQL uses row locking and dialect-specific conflict-safe inserts.

Core invariants:

- `UNIQUE(session_id, student_id)` is enforced by the database.
- Attendance records and recognition events are separate tables.
- Each frame request uses a UUID, and event keys are unique per session/request/face index. Retrying a processed request replays existing events without reapplying attendance.
- Identity is resolved only inside the trusted server recognition pipeline. Client-supplied names, ERP IDs or confidence values cannot mark face attendance.
- All write operations recheck session scope. Closed or past-window sessions reject recognition. Corrections use a separate authorized and audited operation.
- Starting a session snapshots its roster and attendance policy. Closing creates absent records only for missing roster entries. Closing twice is harmless.
- Enrollment withdrawal and biometric withdrawal stop subsequent automatic matching. Active roster history remains retained for academic accounting.
- Completed-session percentages use unique records, with configurable handling of LATE and EXCUSED. Active sessions show pending students rather than preemptively marking them absent.

See [architecture and schema](docs/ARCHITECTURE.md) and [API examples](docs/API.md).

### PostgreSQL and optional Docker

Set `DATABASE_URL` in `backend/.env`, for example:

```dotenv
DATABASE_URL=postgresql+psycopg://faceiq:URL_ENCODED_PASSWORD@127.0.0.1:5432/faceiq
```

The Python dependencies include psycopg 3. The same Alembic migration initializes PostgreSQL. Do not assume that changing the URL migrates existing SQLite records; data migration requires a separately verified export/import.

Optional containers (Docker Desktop required):

```powershell
$env:POSTGRES_PASSWORD = "YOUR_UNIQUE_URL_SAFE_DATABASE_PASSWORD"
$env:ENCRYPTION_KEY = "YOUR_GENERATED_FERNET_KEY"
docker compose up -d db
docker compose run --rm api python scripts/initialize_database.py
docker compose run --rm api python scripts/create_admin.py
docker compose up -d api
.\run_frontend.bat
```

Keep the same encryption key for existing biometric data. The compose API binds only to loopback; the database is not exposed to the host. Container and PostgreSQL deployment have not been executed in this environment. Production hosting additionally needs TLS, a trusted reverse proxy, restricted database access, monitoring, an institution-approved retention process and tested backups. Do not expose the Vite development server publicly.

## Authentication and privacy controls

- Argon2id password hashes, random opaque bearer tokens, hashed token storage, 60-minute expiry by default and server-side logout revocation.
- Tokens are held in browser memory, not localStorage or cookies. Refreshing the page requires login. Cross-site cookie authentication is not used, so there is no cookie-based CSRF channel.
- Backend role/resource checks apply to API and WebSocket connections. WebSocket tokens are sent in the first message, never in URLs, and authorization is checked on each snapshot. Allowed browser origins are explicit.
- Database photographs and template payloads are encrypted using Fernet. Templates never leave the backend. A newly generated deployment key is stored in `backend/.env`; keep this file private and backed up separately.
- Upload bodies are bounded, extensions are not trusted, image dimensions are bounded, metadata is removed, and original filenames are never used for filesystem storage.
- Login and sensitive operations have bounded process-local rate limits. Use one API worker; distributed deployment needs a shared limiter and shared tracking state.
- Consent withdrawal/deactivation erases photograph and template payloads. Replacement erases obsolete embedding payloads and keeps version metadata for auditing.
- Exports escape formula-like text to prevent spreadsheet formula injection.
- Recognition events, corrections, exports, policy changes and biometric lifecycle operations have an audit trail. Audit logs are application-protected but not externally tamper-evident against a database administrator.

Adapt the [institutional privacy notice](docs/PRIVACY-NOTICE.md) before collecting real data. Faces are used only for attendance; no emotion or unrelated profiling is implemented.

### Retention and backup

An administrator can run cleanup from Settings. To schedule cleanup using Windows Task Scheduler:

```bat
.venv\Scripts\python.exe scripts\retention.py
```

Configure the task's Start in folder to the project directory. It removes expired recognition events/auth sessions and expired or withdrawn biometric payloads. Academic attendance and audit records are not automatically deleted. Retention defaults are configurable; records in old backups need a separate expiry policy.

Consistent SQLite backup:

```bat
.venv\Scripts\python.exe scripts\backup_database.py C:\SecureBackups\faceiq-2026-10-11.db
```

Restore: stop both application services; preserve the current database and matching encryption key in a separate backup; replace `storage/faceiq.db` with the selected consistent backup; remove stale `faceiq.db-wal` and `faceiq.db-shm` only after all database connections have closed; restore the matching key securely; run migrations; verify login, record counts and a known template before resuming. For PostgreSQL use `pg_dump -Fc` and `pg_restore` into a separate test database first. Never test restoration over the sole production copy.

## Tests and measurements

```bat
test.bat
.venv\Scripts\python.exe scripts\benchmark.py --frames 80
```

The backend tests use temporary SQLite databases, deterministic mock embeddings and controlled images. They verify authentication, scope, unique ERP IDs, photo validation/encryption, template replacement/deletion, enrollment, session authorization, temporal matching, duplicate prevention under concurrency, replay behavior, ambiguity, finalization, manual corrections, student privacy, authenticated WebSockets and both export formats. Frontend Vitest tests exercise operational labels, pagination, errors and camera lifecycle cleanup.

The benchmark loads the **real verified models** and measures CPU time, memory high-water mark, inference latency and processed FPS. By default the detector input is synthetic non-face noise and the SFace input is a synthetic aligned crop. This is not a live-webcam test and establishes no identification accuracy. Use `--image PATH` with an appropriately consented image for a more representative workload.

For pairwise verification evaluation on private, held-out embeddings:

```bat
.venv\Scripts\python.exe scripts\evaluate_recognition.py C:\PrivateEvaluation\pairs.npz --threshold 0.55 --output C:\PrivateEvaluation\results.json
```

The NPZ contains `left` and `right` arrays of shape `(N,128)` plus `same_person` labels `(N,)`. Include genuine and impostor pairs, separate calibration/evaluation subjects, record collection conditions and review group-specific error rates. The script reports observed false accepts, false rejects, FAR and FRR; it does not evaluate liveness, detection failures, open-set identification or multi-face ambiguity. Do not approve a threshold from the synthetic test fixtures.

Actual measured results, environmental limits and test counts are in [docs/TEST-RESULTS.md](docs/TEST-RESULTS.md) and `docs/performance-results.json`.

## Linux/macOS development

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/configure.py
.venv/bin/python scripts/initialize_database.py
.venv/bin/python scripts/create_admin.py
cd frontend
npm ci
npm run dev
```

In another terminal from the project root:

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1 --ws-max-size 65536
```

## Troubleshooting

| Symptom | Action |
|---|---|
| Python 3.14 / NumPy build errors on Windows | Use the documented Python 3.12 x64 environment. Do not reuse a venv made by another Python version. |
| No model / bad hash | Re-run the official model installer. A Git LFS pointer is not a model. Never disable hash verification. |
| SETUP_REQUIRED photo | Install models, restart backend, open student profile, choose Regenerate template. |
| REVIEW_REQUIRED for every match | Check calibration approval in the session's policy, liveness requirement, ambiguity and photo quality. Settings apply to newly started sessions. |
| No camera permission | Use localhost or HTTPS. Allow camera permission in the browser, close other camera apps, reconnect and choose Enable camera. |
| No eligible faculty in scheduling | Assign an active faculty account to the course first. |
| Cannot enroll | Student must be active and match course department, semester and section exactly. |
| Session cannot start | Check scheduled time, course/faculty activity and another active session for that course. |
| Webcam disconnect | Stop/reconnect the camera and choose Enable camera again. Tracks are released on stop, disconnect, route exit and late permission resolution. |
| Port in use | Stop the previous process in its terminal. Scripts never kill unrelated processes. |
| Lost encryption key | Restore the matching key from secure backup. Without it, encrypted photos/templates are unrecoverable; re-enrollment is required. |
| Login expires / page refresh | Sign in again. Tokens are intentionally not persisted in browser storage. |
| More than 10,000 export rows | Narrow course, student, status or date filters. |

## Known limitations

- Windows batch files are supplied and Windows 3.12 wheel availability was checked. Actual Windows execution and a physical webcam were not available for validation here.
- No measured face identification accuracy or representative FAR/FRR results are included. Institutional calibration and controlled pilot evaluation remain required.
- Liveness/spoof resistance is unavailable. Faculty review and manual attendance are implemented.
- CPU benchmark results come from this Linux execution environment and synthetic inputs; laptop performance will differ.
- Local webcam is implemented. RTSP/IP-camera adapters, multi-campus tenancy, SSO/MFA, automated account recovery and distributed workers are not included.
- Sessions stop accepting recognition at their scheduled end, but faculty/admin must explicitly finalize the absent register. There is no unattended auto-finalization service.
- List pages are paginated. Some course/faculty dropdowns currently show the first 100 authorized entries; very large institutions need searchable remote selectors. Aggregate historical analytics run on demand and should be moved to indexed rollups at large scale.
- Department, program and section are validated profile/course fields rather than independent catalog tables. Roles use a database-constrained enum string; faculty profiles share the User table. These are intentional schema simplifications.
- Academic course identity (code/section/year/semester/department) is immutable once created; archive and create a new section for a different academic identity.
- Biometric deletion removes active database values; it is not a forensic secure-erase guarantee for SQLite pages/WAL or storage media. Backup copies have a separate retention lifecycle. The encrypted key file and database still require OS-level access protection.
- Audit records are not cryptographically signed. Independent security testing and production operational hardening remain outstanding.

## Project layout

See [docs/PROJECT-TREE.txt](docs/PROJECT-TREE.txt) for the complete delivered tree.

```text
FaceIQ-Campus/
  backend/app/          API, policy, security, ORM, recognition and attendance modules
  backend/migrations/  Versioned Alembic schema
  backend/tests/       Deterministic backend regression tests
  frontend/src/        React pages, shared UI, typed API client and camera lifecycle
  scripts/             Setup, admin creation, model acquisition, demo, backup and evaluation
  storage/             Local database/model directory (generated; no student data bundled)
  docs/                Architecture, API examples, privacy, licenses and verification
  install.bat          Windows installation
  run_*.bat            Windows launchers
  test.bat             Backend + frontend tests and build
  compose.yaml         Optional PostgreSQL/API deployment
```
