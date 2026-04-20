import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, type LeaveRequest } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { StatusBadge, formatDateRange } from "../components/common";

export default function MyLeave() {
  const auth = useAuth();
  const user = auth.status === "authenticated" ? auth.user : null;
  const [items, setItems] = useState<LeaveRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user) return;
    try {
      setItems(await api.listLeave({ requester_id: user.id }));
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    }
  }, [user]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!user) return null;

  async function submit(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await api.submitLeave(id);
      await load();
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    } finally {
      setBusyId(null);
    }
  }

  async function cancel(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await api.cancelLeave(id);
      await load();
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <h1>My leave requests</h1>
      <div className="inline" style={{ marginBottom: 12 }}>
        <Link className="button" to="/leave/new">Request leave</Link>
      </div>
      {error && <div className="error" role="alert">{error}</div>}

      {items.length === 0 ? (
        <p className="muted">No leave requests yet.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Dates</th>
              <th>Status</th>
              <th>Submitted</th>
              <th>Decision</th>
              <th>Reason</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((l) => (
              <tr key={l.id}>
                <td>{l.type}</td>
                <td>{formatDateRange(l.start_date, l.end_date)}</td>
                <td><StatusBadge status={l.status} /></td>
                <td>{l.submitted_at ? new Date(l.submitted_at).toLocaleDateString() : "—"}</td>
                <td>{l.decided_at ? new Date(l.decided_at).toLocaleDateString() : "—"}</td>
                <td>{l.reason ?? ""}</td>
                <td>
                  <div className="inline">
                    {l.status === "DRAFT" && (
                      <button disabled={busyId === l.id} onClick={() => submit(l.id)}>
                        Submit
                      </button>
                    )}
                    {!["REJECTED", "CANCELLED", "OVERRIDDEN"].includes(l.status) && (
                      <button className="secondary" disabled={busyId === l.id} onClick={() => cancel(l.id)}>
                        Cancel
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
