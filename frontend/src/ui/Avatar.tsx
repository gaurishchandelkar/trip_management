/** The first character of the first and last words, in any script. */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/u).filter(Boolean);
  const picked = words.length > 1 ? [words[0], words.at(-1)] : words;
  return picked
    .map((word) => Array.from(word ?? "")[0] ?? "")
    .join("")
    .toLocaleUpperCase();
}

/** Decorative: the name is always shown beside it, so screen readers skip it. */
export function Avatar({ name }: { name: string }) {
  return (
    <span className="avatar" aria-hidden="true">
      {initials(name)}
    </span>
  );
}
