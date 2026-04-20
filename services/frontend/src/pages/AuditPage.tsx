import { useCallback, useEffect, useState } from "react";
import { ApiError, api, type AuditEvent } from "../api/client";
import { formatDateTime } from "../components/common";

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [action, setAction] = useState("");
  const [since, setSince] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [verification, setVerification] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    setBusy(true);
    try {
      setEvents(await api.listAudit({
        action: action || undefined,
        since: since || undefined,
        limit: 200,
      }));
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    } finally {
      setBusy(false);
    }
  }, [action, since]);

  useEffect(() => {
    void load();
  }, [load]);

  async function verify() {
    setVerification(null);
    try {
      const r = await api.verifyAudit();
      setVerification(
        r.ok
          ? `Chain verified: ${r.checked} events, no tampering.`
          : `Chain broken at event ${r.first_bad_id ?? "?"} (after ${r.checked} events).`,
      );
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    }
  }

  return (
    <div>
      <h1>Audit log</h1>
      <div className="row" style={{ marginBottom: 12 }}>
        <label>
          Action filter
          <input value={action} onChange={(e) => setAction(e.target.value)} placeholder="leave.approve" />
        </label>
        <label>
          Since
          <input type="date" value={since} onChange={(e) => setSince(e.target.value)} />
        </label>
        <button disabled={busy} onClick={load}>Refresh</button>
        <button className="secondary" onClick={verify}>Verify chain</button>
      </div>
      {error && <div className="error" role="alert">{error}</div>}
      {verification && <div className={verification.startsWith("Chain verified") ? "success" : "error"}>{verification}</div>}

      {events.length === 0 ? (
        <p className="muted">No events.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Seq</th>
              <th>When</th>
              <th>Actor role</th>
              <th>Action</th>
              <th>Target</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id}>
                <td>{e.seq}</td>
                <td>{formatDateTime(e.occurred_at)}</td>
                <td>{e.actor_role ?? "—"}</td>
                <td><code>{e.action}</code></td>
                <td>{e.target_type}{e.target_id ? ` · ${e.target_id.slice(0, 8)}` : ""}</td>
                <td>{e.reason ?? <span className="muted">—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
