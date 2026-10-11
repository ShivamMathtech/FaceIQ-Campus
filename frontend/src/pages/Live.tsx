import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Camera, CameraOff, ScanFace } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useCamera } from "../hooks/useCamera";
import { useAction } from "../hooks/useAction";
import {
  Row,
  Page,
  User,
  useData,
  post,
  getToken,
  dateTime,
} from "../services/api";
import {
  Title,
  Card,
  Stat,
  Badge,
  Table,
  ErrorBox,
  Loading,
  Confirm,
  Modal,
  Select,
  Field,
  Pager,
} from "../components/ui";
export function CorrectionForm({
  row,
  sessionId,
  onClose,
}: {
  row: Row;
  sessionId: string;
  onClose: () => void;
}) {
  const [status, setStatus] = useState(
      row.status === "PENDING" ? "PRESENT" : row.status,
    ),
    [reason, setReason] = useState("");
  const a = useAction();
  return (
    <Modal title={"Attendance correction · " + row.name} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          a.run(
            () =>
              post("/sessions/" + sessionId + "/manual-attendance", {
                student_id: row.student_id,
                status,
                reason,
              }),
            onClose,
          );
        }}
      >
        <ErrorBox error={a.error} />
        <Select
          label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {["PRESENT", "LATE", "ABSENT", "EXCUSED", "REVIEW"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </Select>
        <Field label="Mandatory reason (minimum 5 characters)">
          <textarea
            minLength={5}
            maxLength={500}
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explain identity verification and why this record needs correction."
          />
        </Field>
        <p className="muted">
          The original status, new status, reason, timestamp and your account
          are added to the audit trail.
        </p>
        <div className="form-actions">
          <button disabled={a.busy}>Save audited correction</button>
        </div>
      </form>
    </Modal>
  );
}
export default function Live({ user }: { user: User }) {
  const { id = "" } = useParams();
  const q = useData("/sessions/" + id + "/summary"),
    settings = useData("/settings"),
    cache = useQueryClient(),
    a = useAction();
  const [events, setEvents] = useState<Row[]>([]),
    [end, setEnd] = useState(false),
    [manual, setManual] = useState<Row | null>(null),
    [offset, setOffset] = useState(0),
    [connection, setConnection] = useState("CONNECTING"),
    [interval, setIntervalValue] = useState(800);
  const ws = useRef<WebSocket | null>(null);
  const d = q.data,
    authorized = user.role === "admin" || user.id === d?.faculty_id;
  const isStaff = user.role !== "student";
  const roster = useData<Page>(
    "/sessions/" + id + "/roster?offset=" + offset,
    isStaff,
  );
  const records = useData<Page>("/sessions/" + id + "/attendance", !isStaff);
  const camera = useCamera(id, interval, (data) => {
    setEvents(data.results);
    void cache.invalidateQueries({
      queryKey: ["/sessions/" + id + "/summary"],
    });
    void cache.invalidateQueries({
      queryKey: ["/sessions/" + id + "/roster?offset=" + offset],
    });
  });
  useEffect(() => {
    if (d?.status !== "ACTIVE") camera.stop();
  }, [d?.status]);
  useEffect(() => {
    if (!isStaff || !authorized || !d) return;
    let disposed = false,
      retry: ReturnType<typeof setTimeout>;
    const connect = () => {
      const sock = new WebSocket(
        (location.protocol === "https:" ? "wss:" : "ws:") +
          "//" +
          location.host +
          "/api/ws/sessions/" +
          id,
      );
      ws.current = sock;
      sock.onopen = () => {
        sock.send(JSON.stringify({ token: getToken() }));
        setConnection("CONNECTED");
      };
      sock.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === "snapshot") {
          cache.setQueryData(["/sessions/" + id + "/summary"], data.summary);
          setEvents(data.events);
          void cache.invalidateQueries({
            queryKey: ["/sessions/" + id + "/roster?offset=" + offset],
          });
        }
      };
      sock.onerror = () => setConnection("RECONNECTING");
      sock.onclose = (e) => {
        if (disposed) return;
        setConnection(
          e.code === 4401 || e.code === 4403 ? "UNAUTHORIZED" : "RECONNECTING",
        );
        if (e.code !== 4401 && e.code !== 4403)
          retry = setTimeout(connect, 3000);
      };
    };
    connect();
    return () => {
      disposed = true;
      clearTimeout(retry);
      ws.current?.close();
    };
  }, [id, isStaff, authorized, !!d, offset]);
  useEffect(() => {
    if (ws.current?.readyState === WebSocket.OPEN)
      ws.current.send(
        JSON.stringify({ type: "camera_health", status: camera.status }),
      );
  }, [camera.status]);
  if (q.isLoading) return <Loading />;
  if (!d) return <ErrorBox error={q.error} />;
  const corrections =
    authorized &&
    (user.role === "admin" || settings.data?.policy.faculty_corrections);
  return (
    <>
      <Title
        title={d.course_code + " · Live attendance"}
        sub={d.course_name + " / Section " + d.section + " / " + d.room}
        actions={
          <>
            <Badge>{d.status}</Badge>
            {authorized && d.status === "SCHEDULED" && (
              <button
                disabled={a.busy}
                onClick={() => a.run(() => post("/sessions/" + id + "/start"))}
              >
                Start session
              </button>
            )}
            {authorized && d.status === "ACTIVE" && (
              <button className="danger" onClick={() => setEnd(true)}>
                End & finalize
              </button>
            )}
          </>
        }
      />
      <ErrorBox error={a.error || q.error} />
      <p className="session-id">
        SESSION {id} · {dateTime(d.starts_at)} → {dateTime(d.ends_at)}
      </p>
      <div className="stats">
        <Stat label="Present + late" value={d.present + d.late} />
        <Stat label="Pending" value={d.pending} />
        <Stat
          label="Absent"
          value={d.status === "COMPLETED" ? d.absent : "—"}
          note="Calculated on finalization"
        />
        <Stat
          label="Duplicate events blocked"
          value={d.duplicate_events ?? "—"}
        />
      </div>
      {isStaff && (
        <div className="live-grid">
          <Card
            title="Webcam recognition"
            extra={<Badge>{camera.status}</Badge>}
          >
            <div className="camera-stage">
              <video ref={camera.video} muted playsInline />
              <canvas ref={camera.overlay} />
              {camera.status !== "LIVE" && (
                <div className="camera-placeholder">
                  <ScanFace size={68} />
                  <h2>Ready when you are</h2>
                  <p>Your camera starts only after you choose Enable camera.</p>
                </div>
              )}
              <span className="camera-indicator">
                <span
                  className={
                    camera.status === "LIVE" ? "dot active-dot" : "dot"
                  }
                />
                {camera.status === "LIVE" ? "CAMERA ON" : "CAMERA OFF"}
              </span>
            </div>
            <div className="camera-controls">
              <button
                disabled={
                  !authorized ||
                  d.status !== "ACTIVE" ||
                  !d.recognition.available ||
                  camera.status === "LIVE" ||
                  camera.status === "REQUESTING PERMISSION"
                }
                title={
                  !d.recognition.available
                    ? "Install the models and restart the backend"
                    : d.status !== "ACTIVE"
                      ? "Start the session first"
                      : ""
                }
                onClick={() => void camera.start()}
              >
                <Camera size={17} />
                Enable camera
              </button>
              <button
                className="ghost"
                disabled={camera.status === "OFF"}
                onClick={camera.stop}
              >
                <CameraOff size={17} />
                Stop camera
              </button>
              <Select
                label="Capture width"
                value={camera.resolution}
                disabled={camera.status === "LIVE"}
                onChange={(e) => camera.setResolution(Number(e.target.value))}
              >
                <option value="640">640 px</option>
                <option value="960">960 px</option>
              </Select>
              <Select
                label="Sample interval"
                value={interval}
                disabled={camera.status === "LIVE"}
                onChange={(e) => setIntervalValue(Number(e.target.value))}
              >
                <option value="500">500 ms</option>
                <option value="800">800 ms</option>
                <option value="1200">1200 ms</option>
                <option value="2000">2000 ms</option>
              </Select>
            </div>
            <ErrorBox error={camera.error} />
            <div className="telemetry">
              <span>
                Processed FPS <b>{camera.fps}</b>
              </span>
              <span>
                Inference + matching <b>{camera.latency} ms</b>
              </span>
              <span>
                Live updates <b>{connection}</b>
              </span>
            </div>
            {!d.recognition.available && (
              <p className="notice">
                Model setup required. Run the documented model installer,
                restart the backend and regenerate enrolled templates. Manual
                attendance is available.
              </p>
            )}
            {!d.policy?.calibration_approved && (
              <p className="notice">
                Automatic marking is blocked until the session policy has
                calibrated threshold approval. Configure settings before
                starting a new session.
              </p>
            )}
            <p className="muted">
              Liveness: unavailable.{" "}
              {d.policy?.liveness_required
                ? "Mandatory liveness is enabled; matches require manual review."
                : "Face matching alone cannot reliably reject photographs or video replay."}
            </p>
          </Card>
          <Card
            title="Recognition events"
            extra={<span className="muted">Latest 20</span>}
          >
            <div className="event-feed">
              {events.length ? (
                events.map((e, i) => (
                  <div className="event" key={e.id ?? i}>
                    <div>
                      <strong>{e.name ?? "Unresolved face"}</strong>
                      <small>
                        {e.erp_id ?? "No identity recorded"} ·{" "}
                        {dateTime(e.created_at)}
                      </small>
                    </div>
                    <Badge>{e.status}</Badge>
                    {e.score != null && (
                      <small>
                        Cosine similarity {e.score.toFixed(3)} · not a
                        probability
                      </small>
                    )}
                    {e.quality_error && <small>{e.quality_error}</small>}
                  </div>
                ))
              ) : (
                <div className="empty">
                  Recognition events will appear here. Each event is separate
                  from the attendance register.
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
      <Card title={isStaff ? "Session roster & review" : "Your attendance"}>
        <ErrorBox error={roster.error || records.error} />
        <Table
          rows={(isStaff ? roster : records).data?.items ?? []}
          columns={[
            {
              label: "Student",
              render: (r) => (
                <>
                  <strong>{r.name}</strong>
                  <small>{r.erp_id}</small>
                </>
              ),
            },
            { label: "Status", render: (r) => <Badge>{r.status}</Badge> },
            ...(isStaff
              ? [
                  {
                    label: "Review / correction",
                    render: (r: Row) => (
                      <button
                        className="ghost"
                        disabled={
                          !corrections ||
                          !["ACTIVE", "COMPLETED"].includes(d.status)
                        }
                        title={
                          !corrections
                            ? "Only an authorized administrator or permitted faculty can correct attendance"
                            : ""
                        }
                        onClick={() => setManual(r)}
                      >
                        Review / correct
                      </button>
                    ),
                  },
                ]
              : []),
          ]}
        />
        {isStaff && (
          <Pager
            offset={offset}
            total={roster.data?.total ?? 0}
            onChange={setOffset}
          />
        )}
      </Card>
      {end && (
        <Confirm
          title="End and finalize this session?"
          text="Every roster member without an attendance record will be marked absent. New recognition events will be blocked. Authorized corrections remain possible with a reason."
          busy={a.busy}
          onClose={() => setEnd(false)}
          onConfirm={() =>
            a.run(
              () => post("/sessions/" + id + "/end"),
              () => {
                camera.stop();
                setEnd(false);
              },
            )
          }
        />
      )}{" "}
      {manual && (
        <CorrectionForm
          row={manual}
          sessionId={id}
          onClose={() => setManual(null)}
        />
      )}
    </>
  );
}
