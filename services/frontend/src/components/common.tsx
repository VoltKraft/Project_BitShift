import type { LeaveStatus } from "../api/client";

export function StatusBadge({ status }: { status: string }) {
  const cls = `tag tag-${status.toLowerCase()}`;
  return <span className={cls}>{status.replace(/_/g, " ")}</span>;
}

export function formatDateRange(start: string, end: string): string {
  if (start === end) return start;
  return `${start} → ${end}`;
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export const TERMINAL_LEAVE: LeaveStatus[] = ["APPROVED", "REJECTED", "CANCELLED", "OVERRIDDEN"];

export const ACTIVE_LEAVE: LeaveStatus[] = ["SUBMITTED", "DELEGATE_REVIEW", "TL_REVIEW", "HR_REVIEW"];
