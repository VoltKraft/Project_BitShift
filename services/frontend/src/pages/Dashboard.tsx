import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, type LeaveRequest, type Shift } from "../api/client";
import { useAuth, isTlOrAbove, isHrOrAdmin } from "../auth/AuthProvider";
import { StatusBadge, formatDateRange } from "../components/common";

function addDays(isoDate: string, n: number): string {
  const d = new Date(isoDate + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export default function Dashboard() {
  const auth = useAuth();
  const user = auth.status === "authenticated" ? auth.user : null;
  const [leave, setLeave] = useState<LeaveRequest[]>([]);
  const [inbox, setInbox] = useState<LeaveRequest[]>([]);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    const today = new Date().toISOString().slice(0, 10);
    const in14 = addDays(today, 14);
    Promise.all([
      api.listLeave({ requester_id: user.id }).catch(fail),
      isTlOrAbove(user) ? api.leaveInbox().catch(fail) : Promise.resolve([]),
      user.team_id
        ? api.listShifts({ start: today, end: in14, team_id: user.team_id }).catch(fail)
        : Promise.resolve([]),
    ]).then(([l, i, s]) => {
      setLeave(Array.isArray(l) ? l : []);
      setInbox(Array.isArray(i) ? i : []);
      setShifts(Array.isArray(s) ? s : []);
    });
    function fail(err: unknown) {
      if (err instanceof ApiError) setError(err.detail);
      return [];
    }
  }, [user]);

  if (!user) return null;

  const pending = leave.filter((l) => ["DRAFT", "SUBMITTED", "DELEGATE_REVIEW", "TL_REVIEW", "HR_REVIEW"].includes(l.status));
  const approved = leave.filter((l) => l.status === "APPROVED");

  return (
    <div>
      <h1>Welcome, {user.first_name ?? user.email}</h1>
      <p className="muted">Your role: {user.role}</p>
      {error && <div className="error" role="alert">{error}</div>}

      <div className="card-grid">
        <div className="card">
          <div className="kpi">{pending.length}</div>
          <div className="kpi-label">Pending leave requests</div>
          <Link to="/leave">Review →</Link>
        </div>
        <div className="card">
          <div className="kpi">{approved.length}</div>
          <div className="kpi-label">Approved leave days</div>
          <Link to="/leave">View history →</Link>
        </div>
        {isTlOrAbove(user) && (
          <div className="card">
            <div className="kpi">{inbox.length}</div>
            <div className="kpi-label">Awaiting your approval</div>
            <Link to="/inbox">Open inbox →</Link>
          </div>
        )}
        <div className="card">
          <div className="kpi">{shifts.length}</div>
          <div className="kpi-label">Upcoming team shifts (next 14 days)</div>
          <Link to="/shifts">Open calendar →</Link>
        </div>
      </div>

      <div className="card">
        <h2>Quick actions</h2>
        <div className="inline">
          <Link to="/leave/new" className="button">Request leave</Link>
          <Link to="/preferences" className="button secondary">Update preferences</Link>
          {isTlOrAbove(user) && (
            <Link to="/planner" className="button secondary">Plan shifts</Link>
          )}
          {isHrOrAdmin(user) && (
            <Link to="/reports" className="button secondary">Open reports</Link>
          )}
          <a className="button secondary" href={api.icsUrl(user.id)}>
            Download my calendar (ICS)
          </a>
        </div>
      </div>

      <div className="card">
        <h2>Recent requests</h2>
        {leave.length === 0 ? (
          <p className="muted">No leave history yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Dates</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {leave.slice(0, 5).map((l) => (
                <tr key={l.id}>
                  <td>{l.type}</td>
                  <td>{formatDateRange(l.start_date, l.end_date)}</td>
                  <td><StatusBadge status={l.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
