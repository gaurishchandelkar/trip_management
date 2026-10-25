import { useState } from "react";

import {
  ConflictError,
  InvalidInputError,
  type Member,
  register,
  SignedOutError,
  signIn,
} from "./api";
import { alert, type Feedback, FeedbackMessage, status, UNAVAILABLE } from "./Feedback";
import {
  DISPLAY_NAME_HINT,
  DISPLAY_NAME_MAX_LENGTH,
  isValidDisplayName,
  isValidUserId,
  PASSWORD_MAX_LENGTH,
  USER_ID_HINT,
  USER_ID_MAX_LENGTH,
} from "./validation";

function RegisterForm() {
  const [userId, setUserId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);

  function submit() {
    const id = userId.trim();
    const name = displayName.trim();
    if (!isValidUserId(id)) {
      setFeedback(alert(USER_ID_HINT));
      return;
    }
    if (!isValidDisplayName(name)) {
      setFeedback(alert(DISPLAY_NAME_HINT));
      return;
    }
    register(id, name)
      .then((member) => {
        setFeedback(status(`Registered as ${member.user_id}. You can sign in now.`));
      })
      .catch((error: unknown) => {
        if (error instanceof ConflictError) setFeedback(alert("That user ID is already taken."));
        else if (error instanceof InvalidInputError)
          setFeedback(alert(`${USER_ID_HINT} ${DISPLAY_NAME_HINT}`));
        else setFeedback(alert(UNAVAILABLE));
      });
  }

  return (
    <form
      aria-labelledby="register-heading"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <h2 id="register-heading">Register</h2>
      <label htmlFor="register-user-id">User ID</label>
      <input
        id="register-user-id"
        value={userId}
        maxLength={USER_ID_MAX_LENGTH}
        autoComplete="username"
        onChange={(event) => {
          setUserId(event.target.value);
        }}
      />
      <label htmlFor="register-display-name">Display name</label>
      <input
        id="register-display-name"
        value={displayName}
        maxLength={DISPLAY_NAME_MAX_LENGTH}
        autoComplete="name"
        onChange={(event) => {
          setDisplayName(event.target.value);
        }}
      />
      <button type="submit">Register</button>
      <FeedbackMessage feedback={feedback} />
    </form>
  );
}

function SignInForm({ onSignedIn }: { onSignedIn: (member: Member) => void }) {
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);

  function submit() {
    const id = userId.trim();
    if (!isValidUserId(id) || password === "") {
      setFeedback(alert("Enter your user ID and a password."));
      return;
    }
    signIn(id, password)
      .then(onSignedIn)
      .catch((error: unknown) => {
        if (error instanceof SignedOutError)
          setFeedback(alert("No member has that user ID. Register first."));
        else if (error instanceof InvalidInputError)
          setFeedback(alert("Enter your user ID and a password."));
        else setFeedback(alert(UNAVAILABLE));
      });
  }

  return (
    <form
      aria-labelledby="sign-in-heading"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <h2 id="sign-in-heading">Sign in</h2>
      <label htmlFor="sign-in-user-id">User ID</label>
      <input
        id="sign-in-user-id"
        value={userId}
        maxLength={USER_ID_MAX_LENGTH}
        autoComplete="username"
        onChange={(event) => {
          setUserId(event.target.value);
        }}
      />
      <label htmlFor="sign-in-password">Password</label>
      <input
        id="sign-in-password"
        type="password"
        value={password}
        maxLength={PASSWORD_MAX_LENGTH}
        autoComplete="current-password"
        aria-describedby="password-note"
        onChange={(event) => {
          setPassword(event.target.value);
        }}
      />
      <p id="password-note">Passwords aren&apos;t checked yet.</p>
      <button type="submit">Sign in</button>
      <FeedbackMessage feedback={feedback} />
    </form>
  );
}

export function SignedOut({ onSignedIn }: { onSignedIn: (member: Member) => void }) {
  return (
    <div className="forms">
      <SignInForm onSignedIn={onSignedIn} />
      <RegisterForm />
    </div>
  );
}
