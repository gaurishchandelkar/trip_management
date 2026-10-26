import type { ReactNode } from "react";

/** What an empty list means, and the one thing to do about it. */
export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <p>{message}</p>
      {action}
    </div>
  );
}
