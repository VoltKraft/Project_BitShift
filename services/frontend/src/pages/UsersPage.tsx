import { useCallback, useEffect, useState } from "react";
import { ApiError, api, type Role, type Team, type UserDetail } from "../api/client";

const ROLES: Role[] = ["employee", "team_lead", "hr", "admin"];

export default function UsersPage() {
  const [users, setUsers] = useState<UserDetail[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newFirst, setNewFirst] = useState("");
  const [newLast, setNewLast] = useState("");
  const [newRole, setNewRole] = useState<Role>("employee");
  const [newTeam, setNewTeam] = useState<string>("");

  const load = useCallback(async () => {
    try {
      const [u, t] = await Promise.all([api.listUsers(), api.listTeams()]);
      setUsers(u);
      setTeams(t);
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      await api.createUser({
        email: newEmail.trim().toLowerCase(),
        password: newPassword,
        first_name: newFirst,
        last_name: newLast,
        role: newRole,
        team_id: newTeam || null,
      });
      setInfo(`Created ${newEmail}`);
      setNewEmail("");
      setNewPassword("");
      setNewFirst("");
      setNewLast("");
      setNewRole("employee");
      setNewTeam("");
      await load();
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    } finally {
      setBusy(false);
    }
  }

  async function changeRole(id: string, role: Role) {
    try {
      await api.setRole(id, role, "admin update via UI");
      await load();
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    }
  }

  async function deactivate(id: string) {
    if (!window.confirm("Deactivate this user? They will immediately lose access.")) return;
    try {
      await api.deactivateUser(id);
      await load();
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
    }
  }

  return (
    <div>
      <h1>Users</h1>
      {error && <div className="error" role="alert">{error}</div>}
      {info && <div className="success">{info}</div>}

      <div className="card">
        <h2>Create user</h2>
        <form className="form" onSubmit={createUser}>
          <div className="row">
            <label style={{ flex: 1 }}>
              Email
              <input type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} required />
            </label>
            <label style={{ flex: 1 }}>
              Password (≥ 8 chars)
              <input type="password" minLength={8} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required />
            </label>
          </div>
          <div className="row">
            <label style={{ flex: 1 }}>
              First name
              <input value={newFirst} onChange={(e) => setNewFirst(e.target.value)} />
            </label>
            <label style={{ flex: 1 }}>
              Last name
              <input value={newLast} onChange={(e) => setNewLast(e.target.value)} />
            </label>
          </div>
          <div className="row">
            <label style={{ flex: 1 }}>
              Role
              <select value={newRole} onChange={(e) => setNewRole(e.target.value as Role)}>
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </label>
            <label style={{ flex: 1 }}>
              Team
              <select value={newTeam} onChange={(e) => setNewTeam(e.target.value)}>
                <option value="">— none —</option>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </label>
          </div>
          <button type="submit" disabled={busy}>Create user</button>
        </form>
      </div>

      <div className="card">
        <h2>Directory</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Name</th>
              <th>Role</th>
              <th>Team</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const team = teams.find((t) => t.id === u.team_id);
              return (
                <tr key={u.id}>
                  <td>{u.email}</td>
                  <td>{[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"}</td>
                  <td>
                    <select
                      value={u.role}
                      onChange={(e) => changeRole(u.id, e.target.value as Role)}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                  </td>
                  <td>{team?.name ?? "—"}</td>
                  <td>
                    <button className="danger" onClick={() => deactivate(u.id)}>
                      Deactivate
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
