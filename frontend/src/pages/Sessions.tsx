import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Row,
  Page,
  useData,
  post,
  patch,
  dateTime,
  localInput,
} from "../services/api";
import { useAction } from "../hooks/useAction";
import {
  Title,
  Card,
  Table,
  Badge,
  ErrorBox,
  Modal,
  Input,
  Select,
  Pager,
  Confirm,
} from "../components/ui";
export default function Sessions({ admin = false }: { admin?: boolean }) {
  const [offset, setOffset] = useState(0),
    [status, setStatus] = useState(""),
    [edit, setEdit] = useState<Row | null | undefined>(),
    [cancel, setCancel] = useState<Row | null>(null),
    [form, setForm] = useState<Row>({});
  const q = useData<Page>("/sessions?offset=" + offset + "&status=" + status),
    courses = useData<Page>("/courses?limit=100"),
    teachers = useData<Page>("/faculty?limit=100", admin),
    a = useAction();
  const open = (s: Row | null) => {
    setEdit(s);
    setForm(
      s
        ? {
            course_id: s.course_id,
            faculty_id: s.faculty_id,
            starts_at: localInput(s.starts_at),
            ends_at: localInput(s.ends_at),
            room: s.room,
          }
        : {
            course_id: "",
            faculty_id: "",
            starts_at: localInput(new Date().toISOString()),
            ends_at: localInput(new Date(Date.now() + 3600000).toISOString()),
            room: "",
          },
    );
  };
  const course = courses.data?.items.find((c) => c.id === form.course_id);
  return (
    <>
      <Title
        title="Session manager"
        sub="Schedule classes, open attendance windows, and finalize registers."
        actions={
          admin && (
            <button onClick={() => open(null)}>+ Schedule session</button>
          )
        }
      />
      <ErrorBox error={a.error} />
      <Card>
        <div className="toolbar">
          <Select
            label="Session status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All sessions</option>
            {["SCHEDULED", "ACTIVE", "COMPLETED", "CANCELLED"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </Select>
          <span className="muted">
            Times shown in your browser’s local timezone
          </span>
        </div>
        <ErrorBox error={q.error} />
        <Table
          rows={q.data?.items ?? []}
          columns={[
            {
              label: "Course / section",
              render: (s) => (
                <>
                  <strong>
                    {s.course_code} · {s.section}
                  </strong>
                  <small>{s.course_name}</small>
                </>
              ),
            },
            {
              label: "Faculty / room",
              render: (s) => (
                <>
                  {s.faculty_name}
                  <small>{s.room}</small>
                </>
              ),
            },
            {
              label: "Schedule",
              render: (s) => (
                <>
                  {dateTime(s.starts_at)}
                  <small>Until {dateTime(s.ends_at)}</small>
                </>
              ),
            },
            { label: "Status", render: (s) => <Badge>{s.status}</Badge> },
            {
              label: "Actions",
              render: (s) => (
                <div className="actions">
                  <Link to={"/live/" + s.id}>Open →</Link>
                  {admin && s.status === "SCHEDULED" && (
                    <>
                      <button className="ghost" onClick={() => open(s)}>
                        Edit
                      </button>
                      <button className="ghost" onClick={() => setCancel(s)}>
                        Cancel
                      </button>
                    </>
                  )}
                </div>
              ),
            },
          ]}
        />
        <Pager
          offset={offset}
          total={q.data?.total ?? 0}
          onChange={setOffset}
        />
      </Card>
      {edit !== undefined && (
        <Modal
          title={edit ? "Reschedule session" : "Schedule academic session"}
          onClose={() => setEdit(undefined)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = {
                ...form,
                starts_at: new Date(form.starts_at).toISOString(),
                ends_at: new Date(form.ends_at).toISOString(),
              };
              a.run(
                () =>
                  edit
                    ? patch("/sessions/" + edit.id, data)
                    : post("/sessions", data),
                () => setEdit(undefined),
              );
            }}
          >
            <ErrorBox error={a.error || courses.error || teachers.error} />
            <Select
              label="Course / section"
              required
              value={form.course_id}
              onChange={(e) =>
                setForm({ ...form, course_id: e.target.value, faculty_id: "" })
              }
            >
              <option value="">Select a course</option>
              {courses.data?.items
                .filter((c) => c.active)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} · {c.section} · {c.name}
                  </option>
                ))}
            </Select>
            <Select
              label="Assigned faculty"
              required
              value={form.faculty_id}
              onChange={(e) => setForm({ ...form, faculty_id: e.target.value })}
            >
              <option value="">Select assigned faculty</option>
              {teachers.data?.items
                .filter((f) => f.active && course?.faculty_ids.includes(f.id))
                .map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
            </Select>
            <div className="form-grid">
              <Input
                label="Start (local time)"
                type="datetime-local"
                required
                value={form.starts_at}
                onChange={(e) =>
                  setForm({ ...form, starts_at: e.target.value })
                }
              />
              <Input
                label="End (local time)"
                type="datetime-local"
                required
                value={form.ends_at}
                onChange={(e) => setForm({ ...form, ends_at: e.target.value })}
              />
            </div>
            <Input
              label="Classroom / room"
              required
              value={form.room}
              onChange={(e) => setForm({ ...form, room: e.target.value })}
            />
            <p className="muted">
              Opening is allowed from 15 minutes before the scheduled start.
              Automatic attendance closes at the scheduled end; faculty
              finalizes the register.
            </p>
            <div className="form-actions">
              <button disabled={a.busy}>Save session</button>
            </div>
          </form>
        </Modal>
      )}
      {cancel && (
        <Confirm
          title="Cancel scheduled session?"
          text="This session will not accept attendance. Its scheduling history is retained."
          busy={a.busy}
          onClose={() => setCancel(null)}
          onConfirm={() =>
            a.run(
              () => post("/sessions/" + cancel.id + "/cancel"),
              () => setCancel(null),
            )
          }
        />
      )}
    </>
  );
}
