import { Link } from "react-router-dom";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { useData, Row, dateTime, User } from "../services/api";
import {
  Title,
  Card,
  Stat,
  Table,
  Badge,
  ErrorBox,
  Loading,
} from "../components/ui";
export function Trend({ data }: { data: Row[] }) {
  return (
    <div className="chart">
      {data.length ? (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="cyanArea" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#39d5df" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#39d5df" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1e3049" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: "#90a6c0", fontSize: 11 }} />
            <YAxis domain={[0, 100]} tick={{ fill: "#90a6c0", fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                background: "#101f35",
                border: "1px solid #29405c",
              }}
            />
            <Area
              type="monotone"
              dataKey="percentage"
              stroke="#39d5df"
              strokeWidth={3}
              fill="url(#cyanArea)"
            />
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <div className="empty">
          Complete a session to see attendance trends.
        </div>
      )}
    </div>
  );
}
export default function Dashboard({ user }: { user: User }) {
  const q = useData("/dashboard/summary");
  if (q.isLoading) return <Loading />;
  if (!q.data) return <ErrorBox error={q.error} />;
  const d = q.data;
  return (
    <>
      <Title
        title={`Welcome, ${user.name.split(" ")[0]}`}
        sub="A clear view of every class, every session, every attendance record."
        actions={
          <Link className="button" to="/sessions">
            Open session manager →
          </Link>
        }
      />
      <div className="hero-strip">
        <div className="orb">IQ</div>
        <div>
          <h2>Attendance, with accountability.</h2>
          <p>
            Verified enrollment. One record per session. A traceable audit
            history.
          </p>
        </div>
        <Badge>
          {d.recognition.available ? "MODELS READY" : "MODEL SETUP REQUIRED"}
        </Badge>
      </div>
      <div className="stats">
        <Stat label="Students in scope" value={d.student_count} />
        <Stat label="Academic courses" value={d.course_count} />
        <Stat
          label={user.role === "admin" ? "Faculty accounts" : "Active sessions"}
          value={user.role === "admin" ? d.faculty_count : d.active_sessions}
        />
        <Stat
          label="Attendance rate"
          value={d.overall_percentage + "%"}
          note="Completed sessions only"
        />
      </div>
      <div className="grid-2">
        <Card
          title="Attendance trend"
          extra={<span className="muted">Last 31 observed days · UTC</span>}
        >
          <Trend data={d.daily} />
        </Card>
        <Card title="Today at a glance">
          <div className="today">
            <Stat label="Present + late" value={d.present_today} />
            <Stat
              label="Absent"
              value={d.absent_today}
              note="Finalized registers"
            />
            <Stat label="Active sessions" value={d.active_sessions} />
          </div>
          <p className="notice">
            Face matching is not liveness detection. Faculty review and a manual
            attendance alternative remain available.
          </p>
        </Card>
      </div>
      <Card title="Recent sessions">
        <Table
          rows={d.recent_sessions}
          columns={[
            {
              label: "Course",
              render: (r) => (
                <strong>
                  {r.course_code} · {r.course_name}
                </strong>
              ),
            },
            {
              label: "Section / room",
              render: (r) => r.section + " / " + r.room,
            },
            { label: "Scheduled start", render: (r) => dateTime(r.starts_at) },
            { label: "Status", render: (r) => <Badge>{r.status}</Badge> },
            {
              label: "Open",
              render: (r) => <Link to={"/live/" + r.id}>View session →</Link>,
            },
          ]}
        />
      </Card>
    </>
  );
}
