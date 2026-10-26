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
import { Button } from "./ui/Button";
import { Field } from "./ui/Field";
import {
  DISPLAY_NAME_HINT,
  DISPLAY_NAME_MAX_LENGTH,
  DISPLAY_NAME_RULE,
  isValidDisplayName,
  isValidUserId,
  PASSWORD_MAX_LENGTH,
  USER_ID_HINT,
  USER_ID_MAX_LENGTH,
  USER_ID_RULE,
} from "./validation";

function RegisterForm() {
  const [userId, setUserId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [invalid, setInvalid] = useState<"user-id" | "display-name" | null>(null);
  const [busy, setBusy] = useState(false);

  function submit() {
    const id = userId.trim();
    const name = displayName.trim();
    if (!isValidUserId(id)) {
      setInvalid("user-id");
      setFeedback(alert(USER_ID_HINT));
      return;
    }
    if (!isValidDisplayName(name)) {
      setInvalid("display-name");
      setFeedback(alert(DISPLAY_NAME_HINT));
      return;
    }
    setInvalid(null);
    setBusy(true);
    register(id, name)
      .then((member) => {
        setFeedback(status(`Registered as ${member.user_id}. You can sign in now.`));
      })
      .catch((error: unknown) => {
        if (error instanceof ConflictError) setFeedback(alert("That user ID is already taken."));
        else if (error instanceof InvalidInputError)
          setFeedback(alert(`${USER_ID_HINT} ${DISPLAY_NAME_HINT}`));
        else setFeedback(alert(UNAVAILABLE));
      })
      .finally(() => {
        setBusy(false);
      });
  }

  return (
    <form
      className="card form"
      aria-labelledby="register-heading"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <h2 id="register-heading">Register</h2>
      <Field
        id="register-user-id"
        label="User ID"
        hint={USER_ID_RULE}
        invalid={invalid === "user-id"}
        value={userId}
        maxLength={USER_ID_MAX_LENGTH}
        autoComplete="username"
        onChange={(event) => {
          setUserId(event.target.value);
        }}
      />
      <Field
        id="register-display-name"
        label="Display name"
        hint={DISPLAY_NAME_RULE}
        invalid={invalid === "display-name"}
        value={displayName}
        maxLength={DISPLAY_NAME_MAX_LENGTH}
        autoComplete="name"
        onChange={(event) => {
          setDisplayName(event.target.value);
        }}
      />
      <Button type="submit" busy={busy}>
        Register
      </Button>
      <FeedbackMessage feedback={feedback} />
    </form>
  );
}

function SignInForm({ onSignedIn }: { onSignedIn: (member: Member) => void }) {
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [invalid, setInvalid] = useState<"user-id" | "password" | null>(null);
  const [busy, setBusy] = useState(false);

  function submit() {
    const id = userId.trim();
    if (!isValidUserId(id) || password === "") {
      setInvalid(isValidUserId(id) ? "password" : "user-id");
      setFeedback(alert("Enter your user ID and a password."));
      return;
    }
    setInvalid(null);
    setBusy(true);
    signIn(id, password)
      .then(onSignedIn)
      .catch((error: unknown) => {
        setBusy(false);
        if (error instanceof SignedOutError)
          setFeedback(alert("No member has that user ID. Register first."));
        else if (error instanceof InvalidInputError)
          setFeedback(alert("Enter your user ID and a password."));
        else setFeedback(alert(UNAVAILABLE));
      });
  }

  return (
    <form
      className="card form"
      aria-labelledby="sign-in-heading"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <h2 id="sign-in-heading">Sign in</h2>
      <Field
        id="sign-in-user-id"
        label="User ID"
        hint={USER_ID_RULE}
        invalid={invalid === "user-id"}
        value={userId}
        maxLength={USER_ID_MAX_LENGTH}
        autoComplete="username"
        onChange={(event) => {
          setUserId(event.target.value);
        }}
      />
      <Field
        id="sign-in-password"
        label="Password"
        hint="Passwords aren't checked yet."
        invalid={invalid === "password"}
        type="password"
        value={password}
        maxLength={PASSWORD_MAX_LENGTH}
        autoComplete="current-password"
        onChange={(event) => {
          setPassword(event.target.value);
        }}
      />
      <Button type="submit" variant="primary" busy={busy}>
        Sign in
      </Button>
      <FeedbackMessage feedback={feedback} />
    </form>
  );
}

export function SignedOut({ onSignedIn }: { onSignedIn: (member: Member) => void }) {
  return (
    <div className="signed-out__forms">
      <SignInForm onSignedIn={onSignedIn} />
      <RegisterForm />
    </div>
  );
}
