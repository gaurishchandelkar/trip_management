export interface Greeting {
  message: string;
}

export class InvalidNameError extends Error {
  constructor() {
    super("Invalid name");
    this.name = "InvalidNameError";
  }
}

export async function fetchGreeting(name?: string): Promise<Greeting> {
  const query = name ? `?${new URLSearchParams({ name }).toString()}` : "";
  const response = await fetch(`/api/hello${query}`);
  if (response.status === 422) throw new InvalidNameError();
  if (!response.ok) throw new Error(`Request failed: ${String(response.status)}`);
  return (await response.json()) as Greeting;
}
