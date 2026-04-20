import { useCallback, useEffect, useState } from "react";
import { ApiError, api, type Preference } from "../api/client";
import { useAuth } from "../auth/AuthProvider";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function PreferencesPage() {
  const auth = useAuth();
  const user = auth.status === "authenticated" ? auth.user : null;
  const [items, setItems] = useState<Preference[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [type, setType] = useState<"SHIFT_TIME" | "DAY_OFF" | "PROJECT">("SHIFT_TIME");
  const [shiftPref, setShiftPref] = useState("EARLY");
  const [dayOff, setDayOff] = useState<number[]>([]);
  const today = new Date().toISOString().slice(0, 10);
  const [effectiveFrom, setEffectiveFrom] = useState(today);

  const load = useCallback(async () => {
    if (!user) return;
    try {
      setItems(await api.listPreferences({ user_id: user.id }));
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    }
  }, [user]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!user) return null;
  const userId = user.id;

  async function save() {
    setError(null);
    try {
      const payload: Record<string, unknown> =
        type === "SHIFT_TIME"
          ? { preferred: shiftPref }
          : type === "DAY_OFF"
            ? { weekdays: dayOff }
            : {};
      await api.createPreference({
        user_id: userId,
        preference_type: type,
        payload,
        effective_from: effectiveFrom,
      });
      await load();
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    }
  }

  async function remove(id: string) {
    try {
      await api.deletePreference(id);
      await load();
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    }
  }

  function toggleDay(idx: number) {
    setDayOff((arr) => (arr.includes(idx) ? arr.filter((x) => x !== idx) : [...arr, idx].sort()));
  }

  return (
    <div>
      <h1>My preferences</h1>
      {error && <div className="error" role="alert">{error}</div>}

      <div className="card">
        <h2>Add preference</h2>
        <div className="form">
          <label>
            Type
            <select value={type} onChange={(e) => setType(e.target.value as typeof type)}>
              <option value="SHIFT_TIME">Preferred shift time</option>
              <option value="DAY_OFF">Preferred day(s) off</option>
              <option value="PROJECT">Project</option>
            </select>
          </label>
          {type === "SHIFT_TIME" && (
            <label>
              Preferred
              <select value={shiftPref} onChange={(e) => setShiftPref(e.target.value)}>
                <option value="EARLY">Early</option>
                <option value="LATE">Late</option>
              </select>
            </label>
          )}
          {type === "DAY_OFF" && (
            <fieldset style={{ border: 0, padding: 0 }}>
              <legend className="muted">Weekdays you'd like off</legend>
              <div className="inline">
                {WEEKDAYS.map((d, idx) => (
                  <label key={d} className="inline">
                    <input
                      type="checkbox"
                      checked={dayOff.includes(idx)}
                      onChange={() => toggleDay(idx)}
                    />
                    <span>{d}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          <label>
            Effective from
            <input
              type="date"
              value={effectiveFrom}
              onChange={(e) => setEffectiveFrom(e.target.value)}
            />
          </label>
          <button onClick={save}>Save preference</button>
        </div>
      </div>

      <div className="card">
        <h2>Active preferences</h2>
        {items.length === 0 ? (
          <p className="muted">None yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Payload</th>
                <th>From</th>
                <th>To</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id}>
                  <td>{p.preference_type}</td>
                  <td><code>{JSON.stringify(p.payload)}</code></td>
                  <td>{p.effective_from}</td>
                  <td>{p.effective_to ?? "—"}</td>
                  <td>
                    <button className="danger" onClick={() => remove(p.id)}>Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
