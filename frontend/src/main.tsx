import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  NavLink,
  useLocation,
} from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  LayoutDashboard,
  Users,
  BookOpen,
  CalendarDays,
  ChartNoAxesCombined,
  ClipboardList,
  Settings as SettingsIcon,
  GraduationCap,
  LogOut,
  Eye,
  EyeOff,
  ScanFace,
  Menu,
} from "lucide-react";
import { User, post, setToken } from "./services/api";
import { Input, ErrorBox } from "./components/ui";
import Dashboard from "./pages/Dashboard";
import Students, { StudentProfile } from "./pages/Students";
import { Courses, Faculty } from "./pages/Academic";
import Sessions from "./pages/Sessions";
import Live from "./pages/Live";
import { Records, Analytics } from "./pages/Reports";
import Settings from "./pages/Settings";
import "./style.css";
const client = new QueryClient();
function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [visible, setVisible] = useState(false),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  return (
    <main className="login">
      <section className="login-story">
        <div className="brand">
          <span className="brand-mark">
            <ScanFace />
          </span>
          <span>
            FaceIQ <em>Campus</em>
          </span>
        </div>
        <div className="login-art">
          <div className="scan-ring">
            <ScanFace size={112} strokeWidth={1} />
          </div>
          <span className="floating-tag">01 · VERIFIED ENROLLMENT</span>
          <span className="floating-tag second">02 · UNIQUE ATTENDANCE</span>
        </div>
        <p className="eyebrow">INTELLIGENT ACADEMIC OPERATIONS</p>
        <h1>
          Every student.
          <br />
          Every session.
          <br />
          <span>Accounted for.</span>
        </h1>
        <p>
          Consent-based face attendance, academic session management, and
          reliable records in one connected workspace.
        </p>
      </section>
      <section className="login-form">
        <div className="login-box">
          <p className="eyebrow">WELCOME TO YOUR CAMPUS</p>
          <h2>Sign in to FaceIQ</h2>
          <p>Use your administrator, faculty, or student account.</p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError(null);
              try {
                const r = await post("/auth/login", { email, password });
                setToken(r.access_token);
                onLogin(r.user);
              } catch (e) {
                setError(e);
              } finally {
                setBusy(false);
              }
            }}
          >
            <ErrorBox error={error} />
            <Input
              label="Email address"
              autoComplete="username"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <div className="password-field">
              <Input
                label="Password"
                autoComplete="current-password"
                type={visible ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                className="ghost"
                type="button"
                aria-label={visible ? "Hide password" : "Show password"}
                onClick={() => setVisible(!visible)}
              >
                {visible ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            <button className="login-submit" disabled={busy}>
              {busy ? "Signing in…" : "Sign in securely →"}
            </button>
          </form>
          <div className="login-note">
            <span className="dot active-dot" />
            Backend-enforced access · Encrypted biometrics
          </div>
          <p className="muted">
            First run? Create an administrator using the included setup command.
            No default credentials are installed.
          </p>
        </div>
      </section>
    </main>
  );
}
function Shell({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [menu, setMenu] = useState(false),
    location = useLocation();
  useEffect(() => setMenu(false), [location.pathname]);
  const admin = user.role === "admin";
  const navigation: Array<[string, string, typeof LayoutDashboard]> = [
    ["/", "Overview", LayoutDashboard],
    ["/students", "Students", Users],
    ["/faculty", "Faculty", GraduationCap],
    ["/courses", "Courses", BookOpen],
    ["/sessions", "Sessions", CalendarDays],
    ["/records", "Attendance", ClipboardList],
    ["/analytics", "Analytics", ChartNoAxesCombined],
    ["/settings", "Settings & audit", SettingsIcon],
    ["/profile", "My profile", Users],
  ];
  const links = navigation.filter(([path]) =>
    ["/students", "/faculty", "/settings"].includes(path)
      ? admin
      : path === "/profile"
        ? user.role === "student"
        : true,
  );
  return (
    <div className="shell">
      <aside className={menu ? "sidebar open" : "sidebar"}>
        <div className="brand">
          <span className="brand-mark">
            <ScanFace />
          </span>
          <span>
            FaceIQ <em>Campus</em>
          </span>
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {links.map(([path, label, Icon]) => (
            <NavLink key={path} to={path} end={path === "/"}>
              <Icon size={19} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="privacy-icon">
            <ScanFace size={20} />
          </div>
          <strong>Attendance with trust</strong>
          <p>
            Consent first. Access controlled.
            <br />
            Every change accounted for.
          </p>
          <span>FaceIQ Campus · v1.0</span>
        </div>
      </aside>
      <div className="main-wrap">
        <header>
          <button
            className="mobile-menu ghost"
            aria-label="Toggle navigation"
            onClick={() => setMenu(!menu)}
          >
            <Menu />
          </button>
          <div className="breadcrumb">
            Campus workspace <span>/</span>{" "}
            {links.find(([p]) => p === location.pathname)?.[1] ??
              "Session details"}
          </div>
          <div className="user-menu">
            <span className="initials">
              {user.name.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{user.name}</strong>
              <small>{user.role.toUpperCase()}</small>
            </div>
            <button
              aria-label="Log out"
              className="ghost"
              onClick={async () => {
                try {
                  await post("/auth/logout");
                } finally {
                  onLogout();
                }
              }}
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard user={user} />} />
            <Route
              path="/students"
              element={admin ? <Students /> : <Navigate to="/" />}
            />
            <Route
              path="/students/:id"
              element={admin ? <StudentProfile admin /> : <Navigate to="/" />}
            />
            <Route
              path="/faculty"
              element={admin ? <Faculty /> : <Navigate to="/" />}
            />
            <Route path="/courses" element={<Courses admin={admin} />} />
            <Route path="/sessions" element={<Sessions admin={admin} />} />
            <Route path="/live/:id" element={<Live user={user} />} />
            <Route path="/records" element={<Records />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route
              path="/settings"
              element={admin ? <Settings /> : <Navigate to="/" />}
            />
            <Route
              path="/profile"
              element={
                user.role === "student" ? (
                  <StudentProfile own />
                ) : (
                  <Navigate to="/" />
                )
              }
            />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
          <footer>
            FaceIQ Campus · Biometric attendance with a manual alternative ·
            Session timestamps stored in UTC
          </footer>
        </main>
      </div>
    </div>
  );
}
function App() {
  const [user, setUser] = useState<User | null>(null);
  const logout = () => {
    setToken("");
    client.clear();
    setUser(null);
  };
  useEffect(() => {
    window.addEventListener("session-expired", logout);
    return () => window.removeEventListener("session-expired", logout);
  }, []);
  return user ? (
    <Shell user={user} onLogout={logout} />
  ) : (
    <Login onLogin={setUser} />
  );
}
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
