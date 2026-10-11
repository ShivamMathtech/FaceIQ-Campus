import { useEffect, useState } from "react";
import {
  useData,
  api,
  post,
  Page,
  Row,
  dateTime,
  download,
} from "../services/api";
import { useAction } from "../hooks/useAction";
import {
  Title,
  Card,
  Table,
  ErrorBox,
  Pager,
  Input,
  Field,
  Confirm,
} from "../components/ui";
export default function Settings() {
  const q = useData("/settings"),
    [form, setForm] = useState<Row | null>(null),
    [offset, setOffset] = useState(0),
    [action, setAction] = useState(""),
    [retention, setRetention] = useState(false),
    [message, setMessage] = useState("");
  const logs = useData<Page>(
      "/audit-logs?offset=" + offset + "&action=" + encodeURIComponent(action),
    ),
    a = useAction();
  useEffect(() => {
    if (q.data) setForm(q.data.policy);
  }, [q.data]);
  return (
    <>
      <Title
        title="Settings & accountability"
        sub="Recognition policies, biometric lifecycle, and a traceable operational history."
      />
      <ErrorBox error={a.error || q.error} />
      {message && (
        <p role="status" className="notice">
          {message}
        </p>
      )}
      <div className="grid-2">
        <Card title="Attendance & recognition policy">
          {form && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                a.run(async () => {
                  await api("/settings", {
                    method: "PUT",
                    body: JSON.stringify(form),
                  });
                  setMessage(
                    "Policy saved. New sessions capture the updated policy.",
                  );
                });
              }}
            >
              <div className="form-grid">
                {[
                  [
                    "late_grace_minutes",
                    "Late grace period (minutes)",
                    0,
                    120,
                    1,
                  ],
                  [
                    "recognition_threshold",
                    "Cosine match threshold",
                    0.1,
                    0.99,
                    0.01,
                  ],
                  [
                    "ambiguity_margin",
                    "Minimum top-two margin",
                    0.01,
                    0.5,
                    0.01,
                  ],
                  [
                    "smoothing_frames",
                    "Consecutive matching samples",
                    2,
                    10,
                    1,
                  ],
                  [
                    "event_retention_days",
                    "Recognition event retention (days)",
                    1,
                    365,
                    1,
                  ],
                  [
                    "biometric_retention_days",
                    "Biometric retention (days)",
                    1,
                    3650,
                    1,
                  ],
                ].map(([key, label, min, max, step]) => (
                  <Input
                    key={String(key)}
                    label={String(label)}
                    type="number"
                    min={min}
                    max={max}
                    step={step}
                    required
                    value={form[String(key)]}
                    onChange={(e) =>
                      setForm({ ...form, [key]: Number(e.target.value) })
                    }
                  />
                ))}
              </div>
              {[
                [
                  "faculty_corrections",
                  "Allow assigned faculty to make audited corrections",
                ],
                ["late_counts_present", "Count late attendance as present"],
                [
                  "excused_in_denominator",
                  "Include excused records in attendance denominator",
                ],
                [
                  "liveness_required",
                  "Require liveness verification (currently unavailable; blocks automatic attendance)",
                ],
                [
                  "calibration_approved",
                  "Approve calibrated threshold for automatic attendance",
                ],
              ].map(([key, label]) => (
                <label className="check" key={key}>
                  <input
                    type="checkbox"
                    checked={form[key]}
                    onChange={(e) =>
                      setForm({ ...form, [key]: e.target.checked })
                    }
                  />
                  {label}
                </label>
              ))}
              <Field label="Calibration evidence / evaluation reference">
                <textarea
                  value={form.calibration_note}
                  maxLength={500}
                  minLength={form.calibration_approved ? 10 : 0}
                  required={form.calibration_approved}
                  onChange={(e) =>
                    setForm({ ...form, calibration_note: e.target.value })
                  }
                />
              </Field>
              <p className="muted">
                The default threshold is a starting point, not a measured
                accuracy claim. Evaluate false accepts and false rejects on
                consented representative data before approval.
              </p>
              <button disabled={a.busy}>Save policy</button>
            </form>
          )}
        </Card>
        <Card title="Biometric lifecycle">
          <p>
            Photos and templates are encrypted with the deployment’s Fernet key.
            Replacing a photo invalidates and erases previous template payloads.
          </p>
          <p>
            Consent withdrawal and deactivation delete biometric payloads
            immediately. Academic attendance and audit history are retained.
          </p>
          <p>
            Retention cleanup removes expired events, expired login sessions,
            and biometric data past the configured retention period.
          </p>
          <button className="danger" onClick={() => setRetention(true)}>
            Run retention cleanup
          </button>
          <h3>Model health</h3>
          <p>{q.data?.recognition.message}</p>
          <p className="notice">
            Liveness: UNAVAILABLE. Printed photos, screens, and replay attacks
            are not reliably detected by this application.
          </p>
          <p className="muted">
            Schedule the retention command using Windows Task Scheduler. Backup
            copies need their own expiry and deletion policy.
          </p>
        </Card>
      </div>
      <Card
        title="Audit history"
        extra={
          <button
            className="ghost"
            onClick={() =>
              a.run(() =>
                download(
                  "/audit-logs?format=csv&action=" + encodeURIComponent(action),
                  "faceiq-audit.csv",
                ),
              )
            }
          >
            Export CSV
          </button>
        }
      >
        <div className="toolbar">
          <input
            aria-label="Filter audit actions"
            placeholder="Filter action…"
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setOffset(0);
            }}
          />
        </div>
        <ErrorBox error={logs.error} />
        <Table
          rows={logs.data?.items ?? []}
          columns={[
            {
              label: "Action",
              render: (r) => (
                <>
                  <strong>{r.action}</strong>
                  <small>{r.resource_id}</small>
                </>
              ),
            },
            { label: "Time", render: (r) => dateTime(r.created_at) },
            { label: "Actor", render: (r) => r.actor_id ?? "System" },
            {
              label: "Details",
              render: (r) => (
                <details>
                  <summary>View changes</summary>
                  <pre>{JSON.stringify(r.details, null, 2)}</pre>
                </details>
              ),
            },
          ]}
        />
        <Pager
          offset={offset}
          total={logs.data?.total ?? 0}
          onChange={setOffset}
        />
      </Card>
      {retention && (
        <Confirm
          title="Run retention cleanup?"
          text="Expired recognition events, login sessions and biometric payloads will be permanently removed from the live database according to your configured policy. Academic attendance records remain retained."
          busy={a.busy}
          onClose={() => setRetention(false)}
          onConfirm={() =>
            a.run(
              async () => {
                const r = await post("/settings/retention/run");
                setMessage(
                  `Deleted ${r.events_deleted} events and ${r.biometrics_deleted} biometric registrations.`,
                );
              },
              () => setRetention(false),
            )
          }
        />
      )}
    </>
  );
}
