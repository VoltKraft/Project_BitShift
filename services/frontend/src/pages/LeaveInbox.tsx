import { useCallback, useEffect, useState } from "react";
import { ApiError, api, type LeaveRequest, type UserDetail } from "../api/client";
import { StatusBadge, formatDateRange } from "../components/common";
import { useAuth, isHrOrAdmin } from "../auth/AuthProvider";

export default function LeaveInbox() {
  const auth = useAuth();
  const user = auth.status === "authenticated" ? auth.user : null;
  const [items, setItems] = useState<LeaveRequest[]>([]);
  const [users, setUsers] = useState<Record<string, UserDetail>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [inbox, people] = await Promise.all([api.leaveInbox(), api.listUsers()]);
      setItems(inbox);
      setUsers(Object.fromEntries(people.map((p) => [p.id, p])));
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function decide(id: string, kind: "approve" | "reject") {
    setBusyId(id);
    setError(null);
    setSuccess(null);
    try {
      const reason = reasons[id];
      if (kind === "approve") await api.approveLeave(id, reason);
      else await api.rejectLeave(id, reason);
      setSuccess(`Request ${id.slice(0, 8)}… ${kind}d`);
      await load();
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    } finally {
      setBusyId(null);
    }
  }

  async function override(id: string) {
    const reason = reasons[id];
    if (!reason) {
      setError("Override requires a reason.");
      return;
    }
    setBusyId(id);
    try {
      await api.overrideLeave(id, reason);
      await load();
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <h1>Approvals inbox</h1>
      {error && <div className="error" role="alert">{error}</div>}
      {success && <div className="success">{success}</div>}

      {items.length === 0 ? (
        <p className="muted">Nothing to review.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Requester</th>
              <th>Type</th>
              <th>Dates</th>
              <th>Status</th>
              <th>Reason</th>
              <th>Decision</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((l) => {
              const requester = users[l.requester_id];
              const name = requester
                ? `${requester.first_name ?? ""} ${requester.last_name ?? ""}`.trim() || requester.email
                : l.requester_id.slice(0, 8);
              return (
                <tr key={l.id}>
                  <td>{name}</td>
                  <td>{l.type}</td>
                  <td>{formatDateRange(l.start_date, l.end_date)}</td>
                  <td><StatusBadge status={l.status} /></td>
                  <td>{l.reason ?? <span className="muted">(none)</span>}</td>
                  <td>
                    <input
                      type="text"
                      placeholder="Note / reason"
                      value={reasons[l.id] ?? ""}
                      onChange={(e) => setReasons((r) => ({ ...r, [l.id]: e.target.value }))}
                    />
                  </td>
                  <td>
                    <div className="inline">
                      <button className="approve" disabled={busyId === l.id} onClick={() => decide(l.id, "approve")}>
                        Approve
                      </button>
                      <button className="danger" disabled={busyId === l.id} onClick={() => decide(l.id, "reject")}>
                        Reject
                      </button>
                      {isHrOrAdmin(user) && (
                        <button className="warning" disabled={busyId === l.id} onClick={() => override(l.id)}>
                          Override
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
