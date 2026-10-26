import type { MembershipStatus } from "../api";

type ShownStatus = Exclude<MembershipStatus, "none">;

const STATUS_TEXT: Record<ShownStatus, string> = {
  owner: "You own this group",
  member: "You're a member",
  pending: "Request pending",
};

/** The member's status for a group. The text is always shown, never colour alone. */
export function StatusBadge({ status }: { status: MembershipStatus }) {
  if (status === "none") return null;
  return <span className={`badge badge--${status}`}>{STATUS_TEXT[status]}</span>;
}
