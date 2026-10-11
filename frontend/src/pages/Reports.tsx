import { useState } from "react";
import { Link } from "react-router-dom";
import { useData, Page, Row, download, dateTime } from "../services/api";
import { useAction } from "../hooks/useAction";
import {
  Title,
  Card,
  Table,
  Badge,
  ErrorBox,
  Pager,
  Select,
  Input,
  Stat,
} from "../components/ui";
import { Trend } from "./Dashboard";
export function Records() {
  const [filters, setFilters] = useState({
      course_id: "",
      session_id: "",
      search: "",
      status: "",
      from_date: "",
      to_date: "",
    }),
    [offset, setOffset] = useState(0);
  const qs = new URLSearchParams(filters).toString(),
    q = useData<Page>("/reports/attendance?" + qs + "&offset=" + offset),
    courses = useData<Page>("/courses?limit=100"),
    a = useAction();
  const change = (k: string, v: string) => {
    setFilters({ ...filters, [k]: v });
    setOffset(0);
  };
  return (
    <>
      <Title
        title="Attendance records"
        sub="One authoritative record per student per session. Corrections are made in the session roster."
        actions={
          <>
            {["csv", "xlsx"].map((format) => (
              <button
                key={format}
                className="ghost"
                disabled={a.busy}
                onClick={() =>
                  a.run(() =>
                    download(
                      "/reports/attendance?" + qs + "&format=" + format,
                      "faceiq-attendance." + format,
                    ),
                  )
                }
              >
                Export {format.toUpperCase()}
              </button>
            ))}
          </>
        }
      />
      <ErrorBox error={a.error} />
      <Card>
        <div className="filters">
          <Select
            label="Course"
            value={filters.course_id}
            onChange={(e) => change("course_id", e.target.value)}
          >
            <option value="">All permitted courses</option>
            {courses.data?.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} · {c.section}
              </option>
            ))}
          </Select>
          <Input
            label="Session ID (optional)"
            value={filters.session_id}
            onChange={(e) => change("session_id", e.target.value)}
          />
          <Input
            label="Name / ERP ID"
            value={filters.search}
            onChange={(e) => change("search", e.target.value)}
          />
          <Select
            label="Status"
            value={filters.status}
            onChange={(e) => change("status", e.target.value)}
          >
            <option value="">All statuses</option>
            {["PRESENT", "LATE", "ABSENT", "EXCUSED", "REVIEW"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </Select>
          <Input
            label="From date (UTC)"
            type="date"
            value={filters.from_date}
            onChange={(e) => change("from_date", e.target.value)}
          />
          <Input
            label="To date (UTC)"
            type="date"
            value={filters.to_date}
            onChange={(e) => change("to_date", e.target.value)}
          />
        </div>
        <ErrorBox error={q.error} />
        <Table
          rows={q.data?.items ?? []}
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
            {
              label: "Course / date",
              render: (r) => (
                <>
                  {r.course} / {r.section}
                  <small>{r.date}</small>
                </>
              ),
            },
            { label: "Status", render: (r) => <Badge>{r.status}</Badge> },
            { label: "Source", render: (r) => r.source },
            { label: "Recorded", render: (r) => dateTime(r.recorded_at) },
            {
              label: "Session",
              render: (r) => (
                <Link to={"/live/" + r.session_id}>Open register →</Link>
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
    </>
  );
}
export function Analytics() {
  const [search, setSearch] = useState(""),
    [offset, setOffset] = useState(0);
  const students = useData<Page>(
    "/analytics/students?offset=" +
      offset +
      "&search=" +
      encodeURIComponent(search),
  );
  const q = useData("/analytics/attendance"),
    d = q.data;
  return (
    <>
      <Title
        title="Analytics & reports"
        sub="Attendance policies are captured per session. Duplicate events never contribute to these figures."
      />
      <ErrorBox error={q.error} />
      {d && (
        <>
          <div className="stats">
            <Stat label="Attendance rate" value={d.overall_percentage + "%"} />
            <Stat
              label="Completed student-sessions"
              value={d.completed_denominator}
            />
            <Stat label="Present today" value={d.present_today} />
            <Stat label="Absent today" value={d.absent_today} />
          </div>
          <Card title="Daily attendance · completed sessions">
            <Trend data={d.daily} />
          </Card>
          <Card title="Monthly attendance · last 12 observed months">
            <Trend data={d.monthly} />
          </Card>
          <div className="grid-2">
            <Card title="Course-wise attendance">
              <Table
                rows={d.courses}
                columns={[
                  { label: "Course", render: (r) => r.name },
                  { label: "Rate", render: (r) => r.percentage + "%" },
                  { label: "Late", render: (r) => r.late },
                  { label: "Absent", render: (r) => r.absent },
                ]}
              />
            </Card>
            <Card title="Faculty session statistics">
              <Table
                rows={d.faculty}
                columns={[
                  { label: "Faculty", render: (r) => r.name },
                  { label: "Completed sessions", render: (r) => r.sessions },
                  { label: "Attendance", render: (r) => r.percentage + "%" },
                ]}
              />
            </Card>
          </div>
          <Card title="Student-wise attendance">
            <input
              aria-label="Search student analytics"
              placeholder="Search name or ERP ID…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
            />
            <ErrorBox error={students.error} />
            <Table
              rows={students.data?.items ?? []}
              columns={[
                {
                  label: "Student",
                  render: (r) => (
                    <>
                      {r.name}
                      <small>{r.erp_id}</small>
                    </>
                  ),
                },
                { label: "Attendance", render: (r) => r.percentage + "%" },
                { label: "Student-sessions", render: (r) => r.sessions },
                { label: "Late", render: (r) => r.late },
                { label: "Absent", render: (r) => r.absent },
              ]}
            />
            <Pager
              offset={offset}
              total={students.data?.total ?? 0}
              onChange={setOffset}
            />
          </Card>
        </>
      )}
    </>
  );
}
