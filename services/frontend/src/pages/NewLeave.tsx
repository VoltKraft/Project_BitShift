import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api, type LeaveType, type User, type UserDetail } from "../api/client";
import { useAuth } from "../auth/AuthProvider";

export default function NewLeave() {
  const auth = useAuth();
  const user = auth.status === "authenticated" ? auth.user : null;
  const navigate = useNavigate();

  const today = new Date().toISOString().slice(0, 10);
  const [type, setType] = useState<LeaveType>("VACATION");
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);
  const [reason, setReason] = useState("");
  const [hasCert, setHasCert] = useState(false);
  const [tlId, setTlId] = useState<string>("");
  const [hrId, setHrId] = useState<string>("");
  const [delegateId, setDelegateId] = useState<string>("");
  const [suggestions, setSuggestions] = useState<User[]>([]);
  const [people, setPeople] = useState<UserDetail[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.listUsers().then(setPeople).catch((e: unknown) => {
      if (e instanceof ApiError) setError(e.detail);
    });
  }, []);

  useEffect(() => {
    if (startDate && endDate && startDate <= endDate) {
      api.delegateSuggestions(startDate, endDate).then(setSuggestions).catch(() => {
        // non-fatal
      });
    }
  }, [startDate, endDate]);

  async function submit(e: React.FormEvent, andSubmit: boolean) {
    e.preventDefault();
    if (!user) return;
    setError(null);
    setSubmitting(true);
    try {
      const created = await api.createLeave({
        type,
        start_date: startDate,
        end_date: endDate,
        reason: reason || null,
        approver_delegate_id: delegateId || null,
        approver_tl_id: tlId || null,
        approver_hr_id: hrId || null,
        has_certificate: hasCert,
      });
      if (andSubmit) await api.submitLeave(created.id);
      navigate("/leave");
    } catch (err) {
      if (err instanceof ApiError) setError(err.detail);
      else setError("Could not create request");
    } finally {
      setSubmitting(false);
    }
  }

  const hrPeople = people.filter((p) => p.role === "hr");
  const leadPeople = people.filter((p) => p.role === "team_lead" || p.role === "admin");

  return (
    <div>
      <h1>Request leave</h1>
      <form className="form" onSubmit={(e) => submit(e, true)}>
        <label>
          Leave type
          <select value={type} onChange={(e) => setType(e.target.value as LeaveType)}>
            <option value="VACATION">Vacation</option>
            <option value="SICK">Sickness (auto-approved)</option>
            <option value="OTHER">Other</option>
          </select>
        </label>
        <div className="row">
          <label style={{ flex: 1 }}>
            Start date
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              required
            />
          </label>
          <label style={{ flex: 1 }}>
            End date
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              required
            />
          </label>
        </div>
        <label>
          Reason / comment
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        {type === "SICK" && (
          <label className="inline">
            <input type="checkbox" checked={hasCert} onChange={(e) => setHasCert(e.target.checked)} />
            <span>Medical certificate on file</span>
          </label>
        )}

        {type !== "SICK" && (
          <>
            <label>
              Delegate (optional — peer who reviews first)
              <select value={delegateId} onChange={(e) => setDelegateId(e.target.value)}>
                <option value="">— none —</option>
                {suggestions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.first_name ?? ""} {s.last_name ?? ""} ({s.email}) · suggested
                  </option>
                ))}
                {people
                  .filter((p) => p.id !== user?.id && !suggestions.some((s) => s.id === p.id))
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.first_name ?? ""} {p.last_name ?? ""} ({p.email})
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Team lead
              <select value={tlId} onChange={(e) => setTlId(e.target.value)}>
                <option value="">— none —</option>
                {leadPeople.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.first_name ?? ""} {p.last_name ?? ""} ({p.email})
                  </option>
                ))}
              </select>
            </label>
            <label>
              HR reviewer
              <select value={hrId} onChange={(e) => setHrId(e.target.value)}>
                <option value="">— none —</option>
                {hrPeople.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.first_name ?? ""} {p.last_name ?? ""} ({p.email})
                  </option>
                ))}
              </select>
            </label>
          </>
        )}

        {error && <div className="error" role="alert">{error}</div>}

        <div className="inline">
          <button type="submit" disabled={submitting}>
            {type === "SICK" ? "Submit (auto-approve)" : "Save & submit"}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={submitting}
            onClick={(e) => submit(e, false)}
          >
            Save as draft
          </button>
        </div>
      </form>
    </div>
  );
}
