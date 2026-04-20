import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  api,
  type LeaveSummary,
  type ShiftSummary,
  type Team,
} from "../api/client";
import { isHrOrAdmin, useAuth } from "../auth/AuthProvider";

function addDays(iso: string, n: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export default function Reports() {
  const auth = useAuth();
  const user = auth.status === "authenticated" ? auth.user : null;
  const today = new Date().toISOString().slice(0, 10);
  const [start, setStart] = useState(addDays(today, -30));
  const [end, setEnd] = useState(today);
  const [teamId, setTeamId] = useState<string>("");
  const [teams, setTeams] = useState<Team[]>([]);

  const [leave, setLeave] = useState<LeaveSummary[]>([]);
  const [sick, setSick] = useState<LeaveSummary[]>([]);
  const [shifts, setShifts] = useState<ShiftSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listTeams().then(setTeams).catch(() => undefined);
  }, []);

  const refresh = useCallback(async () => {
    setError(null);
    setBusy(true);
    try {
      const [l, s, sh] = await Promise.all([
        api.leaveSummary(start, end),
        api.sicknessSummary(start, end),
        api.shiftsSummary(start, end, teamId || undefined),
      ]);
      setLeave(l);
      setSick(s);
      setShifts(sh);
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    } finally {
      setBusy(false);
    }
  }, [start, end, teamId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div>
      <h1>Reports</h1>
      <div className="row" style={{ marginBottom: 12 }}>
        <label>
          Start
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          End
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <label>
          Team (shifts only)
          <select value={teamId} onChange={(e) => setTeamId(e.target.value)}>
            <option value="">— all teams —</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </label>
        <button disabled={busy} onClick={refresh}>Refresh</button>
        {isHrOrAdmin(user) && (
          <a className="button secondary" href={api.leaveSummaryCsvUrl(start, end)}>
            Download leave CSV
          </a>
        )}
      </div>
      {error && <div className="error" role="alert">{error}</div>}

      <section className="card">
        <h2>Leave summary</h2>
        {leave.length === 0 ? <p className="muted">No approved leave in range.</p> : (
          <table className="table">
            <thead>
              <tr><th>Employee</th><th>Vacation</th><th>Sickness</th><th>Other</th></tr>
            </thead>
            <tbody>
              {leave.map((r) => (
                <tr key={r.user_id}>
                  <td>{r.user_name}</td>
                  <td>{r.vacation_days}</td>
                  <td>{r.sickness_days}</td>
                  <td>{r.other_days}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <h2>Sickness (F15)</h2>
        {sick.length === 0 ? <p className="muted">No sickness days in range.</p> : (
          <table className="table">
            <thead>
              <tr><th>Employee</th><th>Sickness days</th></tr>
            </thead>
            <tbody>
              {sick.map((r) => (
                <tr key={r.user_id}>
                  <td>{r.user_name}</td>
                  <td>{r.sickness_days}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <h2>Shifts summary</h2>
        {shifts.length === 0 ? <p className="muted">No assignments in range.</p> : (
          <table className="table">
            <thead>
              <tr><th>Employee</th><th>Early</th><th>Late</th><th>Other</th></tr>
            </thead>
            <tbody>
              {shifts.map((r) => (
                <tr key={r.user_id}>
                  <td>{r.user_name}</td>
                  <td>{r.early_count}</td>
                  <td>{r.late_count}</td>
                  <td>{r.other_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
