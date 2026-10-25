import { ConflictError, type ConflictReason } from "./api";

export const UNAVAILABLE = "Something went wrong, please try again.";

export type Feedback = { kind: "alert" | "status"; text: string } | null;

export function alert(text: string): Feedback {
  return { kind: "alert", text };
}

export function status(text: string): Feedback {
  return { kind: "status", text };
}

export function FeedbackMessage({ feedback }: { feedback: Feedback }) {
  if (feedback === null) return null;
  return <p role={feedback.kind}>{feedback.text}</p>;
}

const CONFLICT_MESSAGES: Record<ConflictReason, string> = {
  "user-id-taken": "That user ID is already taken.",
  "group-name-taken": "That group name is already taken.",
  "request-pending": "Request already pending.",
  "already-member": "You're already a member.",
  "limit-reached": "Limit reached.",
  unknown: UNAVAILABLE,
};

/** The UI's own text for a failed call. Server messages are never shown. */
export function messageFor(error: unknown): string {
  return error instanceof ConflictError ? CONFLICT_MESSAGES[error.reason] : UNAVAILABLE;
}
