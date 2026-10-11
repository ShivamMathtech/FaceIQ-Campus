# Verification record

Verification performed in the provided Linux execution environment, Python 3.12.14 and Node.js 24.19.0. No physical webcam or Windows runtime was available. The screenshots use clearly fictional browser-test records; their attendance is an explicitly entered manual test, not a face-recognition result.

## Executed checks

| Check | Actual result |
|---|---|
| Backend pytest suite | **29 passed**, no skipped tests; one Starlette/httpx deprecation warning |
| Frontend Vitest | **7 passed** in two files |
| TypeScript and Vite production build | Passed; separate application, vendor and chart bundles |
| Browser workflow | Passed through real UI and API; zero browser JavaScript errors |
| SQLite Alembic initialization / upgrade | Executed successfully, including the biometric photo-retention timestamp migration |
| Model acquisition | Both pinned official OpenCV models downloaded; sizes and SHA-256 verified |
| Real model execution | YuNet inference and SFace feature extraction executed on synthetic inputs |
| Python dependency audit | `pip-audit` reported no known vulnerabilities for the delivered backend requirements at verification time |
| Frontend dependency audit | `npm audit` reported zero advisories after dependency updates |
| Windows Python 3.12 x64 dependencies | Pip binary-only cross-platform resolution succeeded for all backend dependencies |
| Actual Windows batch execution | **Not executed**; no Windows host available |
| Physical webcam permissions/device behavior | **Not executed on real hardware**; mocked resource-lifecycle tests passed |
| PostgreSQL / Docker execution | **Not executed**; configuration and dialect support provided |
| Representative recognition accuracy, FAR/FRR | **Not measured**; evaluation utility and protocol provided |
| Liveness / spoof resistance | **Unavailable**, explicitly blocked when mandatory |

A clean advisory scan is a point-in-time dependency check, not a penetration test or a guarantee of application security. The Starlette test warning recommends `httpx2`; the pinned httpx test transport still executed successfully. No tests were hidden or skipped to obtain the stated pass counts.

## Backend coverage

The 29 regression tests exercise valid/invalid login, logout revocation, login limiting, role enforcement, course/faculty resource scope, unique ERP constraints, valid/invalid photo ingestion, encrypted storage, template replacement and erasure, consent withdrawal, enrollment validation, session scheduling conflicts and authorization, verified deterministic matches, temporal reset after an unknown sample, duplicate events, request replay, database uniqueness, 12 concurrent recognition requests, recognition/finalization races, non-enrolled identities, unknown/ambiguous/low-confidence matching, closed/past-window sessions, attendance in a new session, absent finalization, percentage integrity, audited correction permissions, authenticated/origin-scoped WebSockets, student privacy, CSV/XLSX exports, formula-injection escaping, missing-model behavior, calibration/liveness gates, retention and monthly/student analytics.

Deterministic face features are injected only by tests into temporary SQLite databases. They demonstrate workflow correctness, not real-world recognition performance. `test.bat` runs these tests, frontend tests and the production build.

## Browser workflow

An isolated SQLite database and a randomly chosen temporary QA administrator password were used. The browser check:

1. Opened the login UI and authenticated.
2. Registered a fictional student with ERP ID.
3. Created a fictional faculty account and course.
4. Enrolled the student and assigned faculty through the course modal.
5. Scheduled and started a session.
6. Received an authenticated WebSocket snapshot.
7. Entered a manual PRESENT correction with an explicit test reason.
8. Finalized the session and opened attendance records.
9. Downloaded CSV through the UI.
10. Opened analytics and audit history, inspected dashboard layouts, and logged out.

The check found a select-control accessible-label issue, which was corrected. The complete workflow then passed with no JavaScript errors. A physical webcam was not activated. `screenshots/login.png` and `screenshots/dashboard.png` show the actual rendered UI from this test.

## Obtained CPU measurements

See `performance-results.json` for machine-readable values and exact input scope. Command: `python scripts/benchmark.py --frames 80` after model warm-up. OpenCV 4.11.0, two configured inference threads, 640×480 synthetic non-face noise, 80 detector samples. CPU percentages count one fully used core as 100%.

| Measurement | Observed |
|---|---:|
| Detector median latency | 9.089 ms |
| Detector p95 latency | 9.848 ms |
| Unthrottled detector throughput | 108.58 processed frames/s |
| Detector process CPU | 187.87% (about 1.88 cores) |
| Process memory high-water mark during detection | 178.12 MiB |
| Change in memory high-water mark during sampled detection | 0.00 MiB |
| SFace median feature latency on synthetic 112×112 crop | 12.310 ms |
| SFace p95 feature latency on synthetic crop | 13.384 ms |
| 1,000-template cosine matching median | 0.656 ms |
| 1,000-template cosine matching p95 | 0.916 ms |

These are isolated CPU microbenchmarks, **not end-to-end webcam FPS**, database throughput, real face-recognition latency or identification accuracy. Zero faces were detected in the noise frames, as expected. SFace execution used a synthetic aligned-size crop solely to execute the network. A real face requires detection, landmark alignment, quality checks, embedding, encrypted-template loading, matching and database processing. Camera UI intentionally samples at a much lower configurable rate, default 800 ms, with a duplicate-only cooldown.

The environment's psutil/proc RSS observations were inconsistent with the loaded model size, so the reported Linux memory value uses the operating system's `resource.getrusage` maximum RSS instead. This is a high-water mark, not a memory-leak proof or a long-duration stability test. Actual Windows laptop results must be measured separately.

## Remaining validation before institutional deployment

Run `install.bat` and `test.bat` on the target Windows laptop, validate camera denial/contention/disconnection with physical devices, test backup restoration, exercise PostgreSQL if chosen, evaluate consented representative recognition data, review institutional privacy requirements, and obtain independent security/operational review. Automatic marking remains disabled by default until an administrator records calibration approval.
