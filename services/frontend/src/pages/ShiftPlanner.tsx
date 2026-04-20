import { useEffect, useState } from "react";
import { ApiError, api, type Team, type User } from "../api/client";

export default function ShiftPlanner() {
  const today = new Date().toISOString().slice(0, 10);
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamId, setTeamId] = useState<string>("");
  const [start, setStart] = useState(today);
  const [end, setEnd] = useState(today);
  const [required, setRequired] = useState(1);
  const [holidaysRaw, setHolidaysRaw] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [unassigned, setUnassigned] = useState<string[]>([]);
  const [users, setUsers] = useState<Record<string, User>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.listTeams().then(setTeams).catch(() => undefined);
    api.listUsers().then((u) => setUsers(Object.fromEntries(u.map((x) => [x.id, x])))).catch(() => undefined);
  }, []);

  async function run() {
    if (!teamId) {
      setError("Pick a team first.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const holidays = holidaysRaw
        .split(/[\s,]+/)
        .map((x) => x.trim())
        .filter(Boolean);
      const r = await api.planShifts({
        team_id: teamId,
        period_start: start,
        period_end: end,
        required_per_shift: required,
        holidays,
      });
      setResult(`Created ${r.shifts_created} shifts · ${r.assignments_created} assignments.`);
      setUnassigned(r.unassigned);
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
      else setError("Planner failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1>Shift planner</h1>
      <p className="muted">
        Generates EARLY / LATE shifts for the selected team across the period (weekdays only, skipping the listed holidays).
      </p>
      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
      >
        <label>
          Team
          <select value={teamId} onChange={(e) => setTeamId(e.target.value)} required>
            <option value="">— pick a team —</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </label>
        <div className="row">
          <label style={{ flex: 1 }}>
            Period start
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} required />
          </label>
          <label style={{ flex: 1 }}>
            Period end
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} required />
          </label>
          <label>
            People per shift
            <input
              type="number"
              min={1}
              max={10}
              value={required}
              onChange={(e) => setRequired(Number(e.target.value))}
            />
          </label>
        </div>
        <label>
          Holidays (comma or whitespace separated ISO dates)
          <input value={holidaysRaw} onChange={(e) => setHolidaysRaw(e.target.value)} placeholder="2026-05-01 2026-05-08" />
        </label>
        <button disabled={busy} type="submit">{busy ? "Planning…" : "Generate plan"}</button>
      </form>

      {error && <div className="error" role="alert">{error}</div>}
      {result && <div className="success">{result}</div>}

      {unassigned.length > 0 && (
        <div className="card">
          <h2>Shifts that could not be staffed</h2>
          <ul>
            {unassigned.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {Object.keys(users).length > 0 && (
        <p className="muted" style={{ marginTop: 12 }}>
          {Object.keys(users).length} people visible to you — the planner ranks them by workload and preferences.
        </p>
      )}
    </div>
  );
}
