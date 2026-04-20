import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, api, type Shift, type ShiftAssignment, type Team, type UserDetail } from "../api/client";
import { useAuth } from "../auth/AuthProvider";

function addDays(iso: string, n: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export default function ShiftCalendar() {
  const auth = useAuth();
  const user = auth.status === "authenticated" ? auth.user : null;
  const today = new Date().toISOString().slice(0, 10);
  const [start, setStart] = useState(today);
  const [end, setEnd] = useState(addDays(today, 14));
  const [teamId, setTeamId] = useState<string>(user?.team_id ?? "");
  const [teams, setTeams] = useState<Team[]>([]);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [assignments, setAssignments] = useState<Record<string, ShiftAssignment[]>>({});
  const [users, setUsers] = useState<Record<string, UserDetail>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listTeams().then(setTeams).catch(() => undefined);
    api.listUsers().then((u) => setUsers(Object.fromEntries(u.map((x) => [x.id, x])))).catch(() => undefined);
  }, []);

  const load = useCallback(async () => {
    if (!teamId) return;
    setError(null);
    try {
      const items = await api.listShifts({ start, end, team_id: teamId });
      setShifts(items);
      const pairs = await Promise.all(
        items.map(async (s) => [s.id, await api.listAssignments(s.id)] as const),
      );
      setAssignments(Object.fromEntries(pairs));
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    }
  }, [start, end, teamId]);

  useEffect(() => {
    void load();
  }, [load]);

  const byDate = useMemo(() => {
    const map: Record<string, Shift[]> = {};
    for (const s of shifts) {
      (map[s.service_date] ??= []).push(s);
    }
    for (const ss of Object.values(map)) {
      ss.sort((a, b) => a.start_time.localeCompare(b.start_time));
    }
    return map;
  }, [shifts]);

  const dates = Object.keys(byDate).sort();

  return (
    <div>
      <h1>Shift calendar</h1>
      <div className="row" style={{ marginBottom: 12 }}>
        <label>
          Team
          <select value={teamId} onChange={(e) => setTeamId(e.target.value)}>
            <option value="">— pick a team —</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </label>
        <label>
          Start
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          End
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <button onClick={load}>Refresh</button>
        {user && (
          <a className="button secondary" href={api.icsUrl(user.id, start, end)}>
            My ICS
          </a>
        )}
      </div>
      {error && <div className="error" role="alert">{error}</div>}

      {dates.length === 0 ? (
        <p className="muted">No shifts in this range.</p>
      ) : (
        <div className="card-grid">
          {dates.map((d) => (
            <div key={d} className="card">
              <h2>{d}</h2>
              {byDate[d].map((s) => {
                const as = assignments[s.id] ?? [];
                const flagged = as.some((a) => a.status === "needs_substitute");
                return (
                  <div key={s.id} style={{ borderTop: "1px solid var(--border)", paddingTop: 8, marginTop: 8 }}>
                    <div className="inline">
                      <strong>{s.shift_type}</strong>
                      <span className="muted">
                        {s.start_time.slice(0, 5)} – {s.end_time.slice(0, 5)}
                      </span>
                      {flagged && <span className="tag tag-rejected">needs substitute</span>}
                    </div>
                    {as.length === 0 ? (
                      <div className="muted">Unassigned</div>
                    ) : (
                      <ul style={{ margin: "4px 0", paddingLeft: 18 }}>
                        {as.map((a) => {
                          const u = users[a.user_id];
                          return (
                            <li key={a.id}>
                              {u ? `${u.first_name ?? ""} ${u.last_name ?? ""}`.trim() || u.email : a.user_id.slice(0, 8)}
                              <span className="muted"> · {a.status}</span>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
