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
