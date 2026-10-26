/** Placeholder rows that reserve the list's space while it loads. */
export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton-list">
      <span className="visually-hidden">Loading…</span>
      {Array.from({ length: rows }, (_, row) => (
        <div key={row} className="skeleton" aria-hidden="true" />
      ))}
    </div>
  );
}
