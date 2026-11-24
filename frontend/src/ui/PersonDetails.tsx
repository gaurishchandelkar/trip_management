import type { Group, Person } from "../api";

/** "@ada": the user ID that tells two people with the same name apart. */
export function userIdLabel(userId: string): string {
  return `@${userId}`;
}

/** "Ada Lovelace (@ada)", for labels that must name one person exactly. */
export function personLabel(person: Person): string {
  return `${person.display_name} (${userIdLabel(person.user_id)})`;
}

/** "Ada Lovelace (@ada)" for a group's owner. */
export function ownerLabel(group: Group): string {
  return personLabel({ user_id: group.owner_user_id, display_name: group.owner_display_name });
}

/** A person's name, their @user-id beside it, and a phone link when the viewer may see it. */
export function PersonDetails({ person }: { person: Person }) {
  return (
    <span className="person__details">
      <span className="person__name">{person.display_name}</span>
      <span className="person__id">{userIdLabel(person.user_id)}</span>
      {person.mobile !== undefined && (
        <a
          className="person__phone"
          href={`tel:${person.mobile}`}
          aria-label={`Call ${personLabel(person)} on ${person.mobile}`}
        >
          {person.mobile}
        </a>
      )}
    </span>
  );
}
