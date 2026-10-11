import { useState } from "react";
import { useData, Page, Row, post, patch, remove } from "../services/api";
import { useAction } from "../hooks/useAction";
import {
  Title,
  Card,
  Table,
  Badge,
  ErrorBox,
  Pager,
  Modal,
  Input,
  Select,
  Confirm,
} from "../components/ui";
export function Faculty() {
  const [offset, setOffset] = useState(0),
    [edit, setEdit] = useState<Row | null | undefined>(),
    [form, setForm] = useState({
      name: "",
      email: "",
      password: "",
      active: true,
    });
  const q = useData<Page>("/faculty?offset=" + offset),
    courses = useData<Page>("/courses?limit=100"),
    a = useAction();
  const open = (r: Row | null) => {
    setEdit(r);
    setForm({
      name: r?.name ?? "",
      email: r?.email ?? "",
      password: "",
      active: r?.active ?? true,
    });
  };
  return (
    <>
      <Title
        title="Faculty & access"
        sub="Faculty accounts are scoped to assigned courses and sessions."
        actions={<button onClick={() => open(null)}>+ Add faculty</button>}
      />
      <Card>
        <ErrorBox error={q.error} />
        <Table
          rows={q.data?.items ?? []}
          columns={[
            {
              label: "Faculty",
              render: (r) => (
                <>
                  <strong>{r.name}</strong>
                  <small>{r.email}</small>
                </>
              ),
            },
            {
              label: "Assigned courses",
              render: (r) =>
                r.course_ids
                  .map(
                    (id: string) =>
                      courses.data?.items.find((c) => c.id === id)?.code ??
                      id.slice(0, 8),
                  )
                  .join(", ") || "None",
            },
            {
              label: "Account",
              render: (r) => <Badge>{r.active ? "ACTIVE" : "INACTIVE"}</Badge>,
            },
            {
              label: "Manage",
              render: (r) => (
                <button className="ghost" onClick={() => open(r)}>
                  Edit account
                </button>
              ),
            },
          ]}
        />
        <Pager
          total={q.data?.total ?? 0}
          offset={offset}
          onChange={setOffset}
        />
      </Card>
      {edit !== undefined && (
        <Modal
          title={edit ? "Edit faculty" : "Create faculty account"}
          onClose={() => setEdit(undefined)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              a.run(
                () =>
                  edit
                    ? patch("/faculty/" + edit.id, {
                        name: form.name,
                        active: form.active,
                        ...(form.password ? { password: form.password } : {}),
                      })
                    : post("/faculty", {
                        name: form.name,
                        email: form.email,
                        password: form.password,
                      }),
                () => setEdit(undefined),
              );
            }}
          >
            <ErrorBox error={a.error} />
            <Input
              label="Full name"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <Input
              label="Email"
              type="email"
              required
              disabled={!!edit}
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            <Input
              label={
                edit
                  ? "New password (leave blank to preserve)"
                  : "Initial password · 12+ characters"
              }
              type="password"
              required={!edit}
              minLength={12}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
            {edit && (
              <Select
                label="Status"
                value={String(form.active)}
                onChange={(e) =>
                  setForm({ ...form, active: e.target.value === "true" })
                }
              >
                <option value="true">Active</option>
                <option value="false">Inactive</option>
              </Select>
            )}
            <p className="muted">
              Assign courses from Course management. No password is displayed
              after saving.
            </p>
            <div className="form-actions">
              <button disabled={a.busy}>Save faculty</button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
function EnrollmentManager({
  course,
  onClose,
}: {
  course: Row;
  onClose: () => void;
}) {
  const [search, setSearch] = useState(""),
    [offset, setOffset] = useState(0),
    [enOffset, setEnOffset] = useState(0),
    [faculty, setFaculty] = useState("");
  const students = useData<Page>(
      "/students?active=true&search=" +
        encodeURIComponent(search) +
        "&offset=" +
        offset,
    ),
    enrolled = useData<Page>(
      "/courses/" + course.id + "/enrollments?offset=" + enOffset,
    ),
    teachers = useData<Page>("/faculty?limit=100"),
    allCourses = useData<Page>(
      "/courses?search=" + encodeURIComponent(course.code) + "&limit=100",
    );
  const current =
    allCourses.data?.items.find((c) => c.id === course.id) ?? course;
  const a = useAction();
  return (
    <Modal
      title={course.code + " · Enrollment & assignments"}
      onClose={onClose}
    >
      <ErrorBox
        error={a.error || students.error || enrolled.error || teachers.error}
      />
      <p className="notice">
        Only students matching {course.department}, semester {course.semester},
        section {course.section} can enroll. New enrollments apply to future
        session rosters.
      </p>
      <h3>Enrolled students</h3>
      <Table
        rows={enrolled.data?.items ?? []}
        columns={[
          { label: "Student", render: (s) => s.name + " · " + s.erp_id },
          {
            label: "Action",
            render: (s) => (
              <button
                className="ghost"
                disabled={a.busy}
                onClick={() =>
                  a.run(() =>
                    remove("/courses/" + course.id + "/enrollments/" + s.id),
                  )
                }
              >
                Remove enrollment
              </button>
            ),
          },
        ]}
      />
      <Pager
        offset={enOffset}
        total={enrolled.data?.total ?? 0}
        onChange={setEnOffset}
      />
      <h3>Add students</h3>
      <input
        aria-label="Find students for enrollment"
        placeholder="Search name or ERP…"
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setOffset(0);
        }}
      />
      <Table
        rows={students.data?.items ?? []}
        columns={[
          {
            label: "Student",
            render: (s) => (
              <>
                {s.name}
                <small>
                  {s.erp_id} · Semester {s.semester} / {s.section}
                </small>
              </>
            ),
          },
          {
            label: "Enroll",
            render: (s) => (
              <button
                className="ghost"
                disabled={
                  a.busy ||
                  s.department !== course.department ||
                  s.semester !== course.semester ||
                  s.section !== course.section
                }
                title="Academic details must match"
                onClick={() =>
                  a.run(() =>
                    post("/courses/" + course.id + "/enrollments", {
                      student_ids: [s.id],
                    }),
                  )
                }
              >
                Enroll
              </button>
            ),
          },
        ]}
      />
      <Pager
        offset={offset}
        total={students.data?.total ?? 0}
        onChange={setOffset}
      />
      <h3>Faculty assignments</h3>
      <Table
        rows={(teachers.data?.items ?? []).filter((f) =>
          current.faculty_ids.includes(f.id),
        )}
        columns={[
          { label: "Faculty", render: (f) => f.name },
          {
            label: "Action",
            render: (f) => (
              <button
                className="ghost"
                disabled={a.busy}
                onClick={() =>
                  a.run(() =>
                    remove("/faculty/assignments/" + course.id + "/" + f.id),
                  )
                }
              >
                Unassign
              </button>
            ),
          },
        ]}
      />
      <div className="toolbar">
        <Select
          label="Assign active faculty"
          value={faculty}
          onChange={(e) => setFaculty(e.target.value)}
        >
          <option value="">Select faculty</option>
          {teachers.data?.items
            .filter((f) => f.active && !current.faculty_ids.includes(f.id))
            .map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
        </Select>
        <button
          disabled={!faculty || a.busy}
          onClick={() =>
            a.run(
              () =>
                post("/faculty/assignments", {
                  course_id: course.id,
                  faculty_id: faculty,
                }),
              () => setFaculty(""),
            )
          }
        >
          Assign
        </button>
      </div>
    </Modal>
  );
}
export function Courses({ admin = false }: { admin?: boolean }) {
  const [offset, setOffset] = useState(0),
    [search, setSearch] = useState(""),
    [edit, setEdit] = useState<Row | null | undefined>(),
    [manage, setManage] = useState<Row | null>(null),
    [archive, setArchive] = useState<Row | null>(null),
    [form, setForm] = useState<Row>({});
  const q = useData<Page>(
      "/courses?offset=" + offset + "&search=" + encodeURIComponent(search),
    ),
    a = useAction();
  const open = (r: Row | null) => {
    setEdit(r);
    setForm(
      r
        ? { ...r }
        : {
            code: "",
            name: "",
            department: "Computer Science",
            semester: 4,
            section: "A",
            academic_year: "2026-2027",
            active: true,
          },
    );
  };
  return (
    <>
      <Title
        title="Academic courses"
        sub="Manage course sections, rosters, and faculty assignments."
        actions={
          admin && <button onClick={() => open(null)}>+ Create course</button>
        }
      />
      <ErrorBox error={a.error} />
      <Card>
        <div className="toolbar">
          <input
            aria-label="Search courses"
            placeholder="Search course name or code…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
        </div>
        <ErrorBox error={q.error} />
        <Table
          rows={q.data?.items ?? []}
          columns={[
            {
              label: "Course",
              render: (c) => (
                <>
                  <strong>{c.code}</strong>
                  <small>{c.name}</small>
                </>
              ),
            },
            {
              label: "Academic details",
              render: (c) => (
                <>
                  {c.department}
                  <small>
                    Semester {c.semester} · {c.section} · {c.academic_year}
                  </small>
                </>
              ),
            },
            { label: "Enrolled", render: (c) => c.enrolled_count },
            {
              label: "Status",
              render: (c) => <Badge>{c.active ? "ACTIVE" : "ARCHIVED"}</Badge>,
            },
            ...(admin
              ? [
                  {
                    label: "Actions",
                    render: (c: Row) => (
                      <div className="actions">
                        <button className="ghost" onClick={() => setManage(c)}>
                          Manage
                        </button>
                        <button className="ghost" onClick={() => open(c)}>
                          Edit
                        </button>
                        <button className="ghost" onClick={() => setArchive(c)}>
                          {c.active ? "Archive" : "Restore"}
                        </button>
                      </div>
                    ),
                  },
                ]
              : []),
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
          title={edit ? "Edit course" : "Create academic course"}
          onClose={() => setEdit(undefined)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              a.run(
                () =>
                  edit
                    ? patch("/courses/" + edit.id, {
                        name: form.name,
                        active: form.active,
                      })
                    : post("/courses", form),
                () => setEdit(undefined),
              );
            }}
          >
            <ErrorBox error={a.error} />
            <div className="form-grid">
              {[
                ["code", "Course code"],
                ["name", "Course name"],
                ["department", "Department"],
                ["section", "Section"],
                ["academic_year", "Academic year"],
              ].map(([key, label]) => (
                <Input
                  key={key}
                  label={label}
                  required
                  disabled={!!edit && key !== "name"}
                  value={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                />
              ))}
              <Input
                label="Semester"
                required
                type="number"
                min="1"
                max="20"
                disabled={!!edit}
                value={form.semester}
                onChange={(e) =>
                  setForm({ ...form, semester: Number(e.target.value) })
                }
              />
            </div>
            {edit && (
              <p className="muted">
                Academic identity is immutable. Create a new course section for
                a different semester or year.
              </p>
            )}
            <div className="form-actions">
              <button disabled={a.busy}>Save course</button>
            </div>
          </form>
        </Modal>
      )}
      {manage && (
        <EnrollmentManager course={manage} onClose={() => setManage(null)} />
      )}{" "}
      {archive && (
        <Confirm
          title={archive.active ? "Archive course?" : "Restore course?"}
          text="Academic records remain retained. Active sessions must be completed before archiving."
          onClose={() => setArchive(null)}
          busy={a.busy}
          onConfirm={() =>
            a.run(
              () =>
                patch("/courses/" + archive.id, { active: !archive.active }),
              () => setArchive(null),
            )
          }
        />
      )}
    </>
  );
}
