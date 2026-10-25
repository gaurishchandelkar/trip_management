import { useEffect, useState } from "react";

import { fetchGreeting, InvalidNameError } from "./api";

export const NAME_MAX_LENGTH = 50;

type State =
  | { status: "loading" }
  | { status: "ready"; message: string }
  | { status: "invalid" }
  | { status: "error"; error: string };

function loadGreeting(setState: (state: State) => void, name?: string) {
  setState({ status: "loading" });
  fetchGreeting(name)
    .then((greeting) => {
      setState({ status: "ready", message: greeting.message });
    })
    .catch((error: unknown) => {
      setState(
        error instanceof InvalidNameError
          ? { status: "invalid" }
          : { status: "error", error: String(error) },
      );
    });
}

export function App() {
  const [state, setState] = useState<State>({ status: "loading" });
  const [name, setName] = useState("");

  useEffect(() => {
    loadGreeting(setState);
  }, []);

  return (
    <main>
      {state.status === "loading" && <p>Loading…</p>}
      {state.status === "ready" && <h1>{state.message}</h1>}
      {state.status === "invalid" && (
        <p role="alert">
          Please enter a valid name (letters, spaces, hyphens and apostrophes, up to{" "}
          {NAME_MAX_LENGTH} characters).
        </p>
      )}
      {state.status === "error" && <p role="alert">Could not load greeting: {state.error}</p>}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          loadGreeting(setState, name.trim());
        }}
      >
        <label htmlFor="name">Your name</label>{" "}
        <input
          id="name"
          value={name}
          maxLength={NAME_MAX_LENGTH}
          onChange={(event) => {
            setName(event.target.value);
          }}
        />{" "}
        <button type="submit">Greet</button>
      </form>
    </main>
  );
}
