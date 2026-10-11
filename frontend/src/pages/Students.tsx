import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  api,
  post,
  patch,
  remove,
  useData,
  Page,
  Row,
  getToken,
  dateTime,
} from "../services/api";
import { useAction } from "../hooks/useAction";
import {
  Title,
  Card,
  Table,
  Badge,
  ErrorBox,
  Loading,
  Pager,
  Modal,
  Input,
  Select,
  Field,
  Confirm,
} from "../components/ui";
export function Photo({ student }: { student: Row }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    setUrl("");
    if (!student.has_photo) return;
    let alive = true,
      objectUrl = "";
    fetch("/api/students/" + student.id + "/photo", {
      headers: { Authorization: "Bearer " + getToken() },
    })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.blob();
      })
      .then((b) => {
        objectUrl = URL.createObjectURL(b);
        if (alive) setUrl(objectUrl);
        else URL.revokeObjectURL(objectUrl);
      })
      .catch(() => {});
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [student.id, student.has_photo, student.updated_at]);
  return url ? (
    <img className="avatar" src={url} alt="Student photograph" />
  ) : (
    <span className="avatar initials">
      {student.name?.slice(0, 2).toUpperCase()}
    </span>
  );
}
const empty = {
  name: "",
  erp_id: "",
  email: "",
  department: "Computer Science",
  program: "B.Tech",
  semester: 4,
  section: "A",
  active: true,
  consent: false,
};
export function StudentForm({
  student,
  onClose,
}: {
  student?: Row;
  onClose: () => void;
}) {
  const [form, setForm] = useState<Row>(
      student
        ? Object.fromEntries(Object.keys(empty).map((k) => [k, student[k]]))
        : empty,
    ),
    [id, setId] = useState(student?.id),
    [photo, setPhoto] = useState<File | null>(null),
    [preview, setPreview] = useState(""),
    [course, setCourse] = useState("");
  const a = useAction(),
    courses = useData<Page>("/courses?limit=100");
  useEffect(() => {
    if (!photo) return;
    const u = URL.createObjectURL(photo);
    setPreview(u);
    return () => URL.revokeObjectURL(u);
  }, [photo]);
  const change = (k: string, v: unknown) => setForm({ ...form, [k]: v });
  const save = () =>
    a.run(async () => {
      let sid = id;
      if (!sid) {
        const created = await post("/students", form);
        sid = created.id;
        setId(sid);
      } else await patch("/students/" + sid, form);
      if (photo) {
        const fd = new FormData();
        fd.append("file", photo);
        await post("/students/" + sid + "/photo", fd);
      }
      if (course)
        await post("/courses/" + course + "/enrollments", {
          student_ids: [sid],
        });
    }, onClose);
  return (
    <Modal
      title={student ? "Edit student profile" : "Register student"}
      onClose={onClose}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        <ErrorBox error={a.error} />
        <div className="form-grid">
          {[
            ["name", "Full name"],
            ["erp_id", "Unique ERP ID"],
            ["email", "Email (optional)"],
            ["department", "Department"],
            ["program", "Program"],
            ["section", "Section"],
          ].map(([key, label]) => (
            <Input
              key={key}
              label={label}
              value={form[key]}
              required={key !== "email"}
              type={key === "email" ? "email" : "text"}
              maxLength={key === "erp_id" ? 50 : 120}
              onChange={(e) => change(key, e.target.value)}
            />
          ))}
          <Input
            label="Semester"
            type="number"
            min="1"
            max="20"
            required
            value={form.semester}
            onChange={(e) => change("semester", Number(e.target.value))}
          />
          <Select
            label="Enrollment status"
            value={String(form.active)}
            onChange={(e) => change("active", e.target.value === "true")}
          >
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </Select>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={form.consent}
            onChange={(e) => change("consent", e.target.checked)}
          />
          Documented consent to campus attendance face processing (notice v1)
        </label>
        <p className="muted">
          Use only for attendance. Students can choose manual attendance and
          withdraw consent. Withdrawal or deactivation deletes the photograph
          and template.
        </p>
        <Field label="Photograph · JPG/PNG · up to 5 MiB">
          <input
            type="file"
            accept="image/jpeg,image/png"
            disabled={!form.consent}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f && f.size > 5 * 1024 * 1024) {
                a.setError(new Error("Maximum photograph size is 5 MiB"));
                return;
              }
              setPhoto(f ?? null);
            }}
          />
        </Field>
        {preview && (
          <img
            className="photo-preview"
            src={preview}
            alt="New photograph preview"
          />
        )}
        <p className="muted">
          Exactly one clear face, even lighting, no blur. Face quality is
          checked when models are installed; otherwise the photo remains pending
          setup.
        </p>
        {!student && (
          <Select
            label="Enroll into a course (optional, matching academic details required)"
            value={course}
            onChange={(e) => setCourse(e.target.value)}
          >
            <option value="">Choose later</option>
            {courses.data?.items
              .filter((c) => c.active)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} · {c.section}
                </option>
              ))}
          </Select>
        )}
        <div className="form-actions">
          <button type="button" className="ghost" onClick={onClose}>
            Cancel
          </button>
          <button disabled={a.busy}>
            {a.busy ? "Validating & saving…" : "Save student"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
export default function Students() {
  const [search, setSearch] = useState(""),
    [active, setActive] = useState(""),
    [offset, setOffset] = useState(0),
    [edit, setEdit] = useState<Row | null | undefined>(undefined);
  const q = useData<Page>(
    "/students?offset=" +
      offset +
      "&search=" +
      encodeURIComponent(search) +
      (active ? "&active=" + active : ""),
  );
  return (
    <>
      <Title
        title="Student directory"
        sub="Enrollment identities, consent, and protected biometric registrations."
        actions={
          <button onClick={() => setEdit(null)}>+ Register student</button>
        }
      />
      <Card>
        <div className="toolbar">
          <input
            aria-label="Search students"
            placeholder="Search name or ERP ID…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
          <Select
            label="Enrollment filter"
            value={active}
            onChange={(e) => {
              setActive(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All students</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </Select>
          <span className="muted">{q.data?.total ?? 0} students</span>
        </div>
        <ErrorBox error={q.error} />
        {q.isLoading ? (
          <Loading />
        ) : (
          <Table
            rows={q.data?.items ?? []}
            columns={[
              {
                label: "Student",
                render: (s) => (
                  <div className="person">
                    <Photo student={s} />
                    <div>
                      <Link to={"/students/" + s.id}>{s.name}</Link>
                      <small>{s.erp_id}</small>
                    </div>
                  </div>
                ),
              },
              {
                label: "Academic details",
                render: (s) => (
                  <>
                    {s.department}
                    <small>
                      Semester {s.semester} · Section {s.section}
                    </small>
                  </>
                ),
              },
              {
                label: "Biometric status",
                render: (s) => <Badge>{s.biometric_status}</Badge>,
              },
              {
                label: "Enrollment",
                render: (s) => (
                  <Badge>{s.active ? "ACTIVE" : "INACTIVE"}</Badge>
                ),
              },
              {
                label: "Actions",
                render: (s) => (
                  <button className="ghost" onClick={() => setEdit(s)}>
                    Edit
                  </button>
                ),
              },
            ]}
          />
        )}
        <Pager
          offset={offset}
          total={q.data?.total ?? 0}
          onChange={setOffset}
        />
      </Card>
      {edit !== undefined && (
        <StudentForm
          student={edit ?? undefined}
          onClose={() => setEdit(undefined)}
        />
      )}
    </>
  );
}
export function StudentProfile({
  admin = false,
  own = false,
}: {
  admin?: boolean;
  own?: boolean;
}) {
  const { id } = useParams();
  const me = useData<Page>("/students?limit=1", own);
  const sid = own ? me.data?.items[0]?.id : id;
  const q = useData("/students/" + sid, !!sid);
  const stats = useData<Page>("/analytics/students?student_id=" + sid, !!sid);
  const a = useAction();
  const [edit, setEdit] = useState(false),
    [erase, setErase] = useState(false),
    [account, setAccount] = useState(false);
  const [creds, setCreds] = useState({ name: "", email: "", password: "" });
  const records = useData<Page>(
    "/reports/attendance?search=" +
      encodeURIComponent(q.data?.erp_id ?? "") +
      "&limit=25",
    !!q.data,
  );
  if (q.isLoading || (me.isLoading && own)) return <Loading />;
  if (!q.data)
    return (
      <ErrorBox error={q.error || me.error || "No linked student profile"} />
    );
  const s = q.data;
  return (
    <>
      <Title
        title={s.name}
        sub={"ERP " + s.erp_id + " · " + s.program + " · " + s.department}
        actions={
          admin && <button onClick={() => setEdit(true)}>Edit profile</button>
        }
      />
      <ErrorBox error={a.error} />
      <div className="grid-2">
        <Card title="Student identity">
          <div className="profile-head">
            <Photo student={s} />
            <div>
              <h2>{s.name}</h2>
              <p>{s.email || "No email provided"}</p>
              <Badge>{s.active ? "ACTIVE" : "INACTIVE"}</Badge>
            </div>
          </div>
          <dl>
            <dt>Semester / section</dt>
            <dd>
              {s.semester} / {s.section}
            </dd>
            <dt>Attendance (completed sessions)</dt>
            <dd>{stats.data?.items[0]?.percentage ?? 0}%</dd>
            <dt>Biometric status</dt>
            <dd>
              <Badge>{s.biometric_status}</Badge>
            </dd>
            <dt>Consent</dt>
            <dd>
              {s.consent
                ? "Documented " + dateTime(s.consent_at)
                : "Not granted"}
            </dd>
          </dl>
          {admin && (
            <div className="actions">
              <button
                className="ghost"
                disabled={!s.has_photo || a.busy}
                title={!s.has_photo ? "Upload a photograph first" : ""}
                onClick={() =>
                  a.run(() =>
                    post(
                      "/students/" + s.id + "/biometric-template/regenerate",
                    ),
                  )
                }
              >
                Regenerate template
              </button>
              <button className="danger" onClick={() => setErase(true)}>
                Withdraw consent & delete biometrics
              </button>
              {!s.user_id && (
                <button
                  className="ghost"
                  onClick={() => {
                    setCreds({ name: s.name, email: s.email, password: "" });
                    setAccount(true);
                  }}
                >
                  Create student login
                </button>
              )}
            </div>
          )}
        </Card>
        <Card title="Enrolled courses">
          <Table
            rows={s.enrollments}
            columns={[
              { label: "Course", render: (c) => c.code + " · " + c.name },
              { label: "Section", render: (c) => c.section },
            ]}
          />
          <h3>Template history</h3>
          <Table
            rows={s.templates}
            columns={[
              { label: "Version", render: (t) => "v" + t.version },
              { label: "Model", render: (t) => t.model },
              {
                label: "State",
                render: (t) => (
                  <Badge>{t.active ? "ACTIVE" : "INVALIDATED"}</Badge>
                ),
              },
            ]}
          />
        </Card>
      </div>
      <Card title="Recent attendance (up to 25 records)">
        <ErrorBox error={records.error} />
        <Table
          rows={records.data?.items ?? []}
          columns={[
            { label: "Course", render: (r) => r.course },
            { label: "Date", render: (r) => r.date },
            { label: "Status", render: (r) => <Badge>{r.status}</Badge> },
          ]}
        />
        <Link to="/records">Open full attendance history →</Link>
      </Card>
      <Card title="Profile change history">
        <Table
          rows={s.history}
          columns={[
            { label: "Action", render: (r) => r.action },
            { label: "Time", render: (r) => dateTime(r.created_at) },
            {
              label: "Details",
              render: (r) => <pre>{JSON.stringify(r.details, null, 2)}</pre>,
            },
          ]}
        />
      </Card>
      {edit && <StudentForm student={s} onClose={() => setEdit(false)} />}{" "}
      {erase && (
        <Confirm
          title="Delete biometric data?"
          text="This removes encrypted photos and templates and withdraws consent. Academic attendance history is retained. Manual attendance remains available."
          onClose={() => setErase(false)}
          busy={a.busy}
          onConfirm={() =>
            a.run(
              () => remove("/students/" + s.id + "/biometric-template"),
              () => setErase(false),
            )
          }
        />
      )}
      {account && (
        <Modal
          title="Create read-only student account"
          onClose={() => setAccount(false)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              a.run(
                () => post("/students/" + s.id + "/account", creds),
                () => setAccount(false),
              );
            }}
          >
            <ErrorBox error={a.error} />
            <Input
              label="Name"
              required
              value={creds.name}
              onChange={(e) => setCreds({ ...creds, name: e.target.value })}
            />
            <Input
              label="Email"
              type="email"
              required
              value={creds.email}
              onChange={(e) => setCreds({ ...creds, email: e.target.value })}
            />
            <Input
              label="Initial password"
              type="password"
              required
              minLength={12}
              autoComplete="new-password"
              value={creds.password}
              onChange={(e) => setCreds({ ...creds, password: e.target.value })}
            />
            <button disabled={a.busy}>Create account</button>
          </form>
        </Modal>
      )}
    </>
  );
}
