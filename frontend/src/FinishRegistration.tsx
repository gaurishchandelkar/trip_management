import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";

import {
  completeRegistration,
  ConflictError,
  getPendingRegistration,
  InvalidInputError,
  type Member,
  SignedOutError,
} from "./api";
import { alert, type Feedback, FeedbackMessage, messageFor, UNAVAILABLE } from "./Feedback";
import { Button } from "./ui/Button";
import { Field } from "./ui/Field";
import { Skeleton } from "./ui/Skeleton";
import { useDocumentTitle } from "./useDocumentTitle";
import {
  DISPLAY_NAME_HINT,
  DISPLAY_NAME_MAX_LENGTH,
  DISPLAY_NAME_RULE,
  isValidDisplayName,
  isValidMobile,
  isValidUserId,
  MOBILE_HINT,
  MOBILE_MAX_LENGTH,
  MOBILE_RULE,
  USER_ID_HINT,
  USER_ID_MAX_LENGTH,
  USER_ID_RULE,
} from "./validation";

type Pending =
  { status: "loading" } | { status: "ready"; returnTo: string } | { status: "unavailable" };

type FieldName = "user-id" | "display-name" | "mobile";

/** The UI's own check of each field, in form order: the first failing field and its hint. */
function firstInvalid(userId: string, displayName: string, mobile: string) {
  if (!isValidUserId(userId)) return { field: "user-id", hint: USER_ID_HINT } as const;
  if (!isValidDisplayName(displayName))
    return { field: "display-name", hint: DISPLAY_NAME_HINT } as const;
  if (!isValidMobile(mobile)) return { field: "mobile", hint: MOBILE_HINT } as const;
  return null;
}

/**
 * After Google sign-in, a new person picks a user ID, a display name and their mobile number.
 * Shown at /register/complete while signed out; the pending registration lives in a cookie.
 */
export function FinishRegistration({ onSignedIn }: { onSignedIn: (member: Member) => void }) {
  useDocumentTitle("Finish registering");
  const navigate = useNavigate();
  const [pending, setPending] = useState<Pending>({ status: "loading" });
  const [userId, setUserId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [mobile, setMobile] = useState("");
  const [invalid, setInvalid] = useState<FieldName | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);

  // No usable pending registration: back to sign-in, which says it expired.
  const expired = useCallback(() => {
    void navigate("/?sign_in=expired", { replace: true });
  }, [navigate]);

  useEffect(() => {
    getPendingRegistration()
      .then((registration) => {
        setDisplayName(registration.display_name);
        setPending({ status: "ready", returnTo: registration.return_to });
      })
      .catch((error: unknown) => {
        if (error instanceof SignedOutError) expired();
        else setPending({ status: "unavailable" });
      });
  }, [expired]);

  function submit(returnTo: string) {
    const id = userId.trim();
    const name = displayName.trim();
    const number = mobile.trim();
    const failure = firstInvalid(id, name, number);
    if (failure !== null) {
      setInvalid(failure.field);
      setFeedback(alert(failure.hint));
      return;
    }
    setInvalid(null);
    setBusy(true);
    completeRegistration(id, name, number)
      .then((member) => {
        void navigate(returnTo, { replace: true });
        onSignedIn(member);
      })
      .catch((error: unknown) => {
        setBusy(false);
        if (error instanceof SignedOutError) {
          expired();
        } else if (error instanceof ConflictError && error.reason === "user-id-taken") {
          setInvalid("user-id");
          setFeedback(alert(messageFor(error)));
        } else if (error instanceof InvalidInputError) {
          setFeedback(alert(`${USER_ID_HINT} ${DISPLAY_NAME_HINT} ${MOBILE_HINT}`));
        } else {
          setFeedback(alert(messageFor(error)));
        }
      });
  }

  if (pending.status === "loading") return <Skeleton rows={2} />;
  if (pending.status === "unavailable") return <FeedbackMessage feedback={alert(UNAVAILABLE)} />;
  const { returnTo } = pending;

  return (
    <form
      className="card form finish-registration"
      aria-labelledby="finish-registration-heading"
      onSubmit={(event) => {
        event.preventDefault();
        submit(returnTo);
      }}
    >
      <h2 id="finish-registration-heading">Finish registering</h2>
      <p>You&apos;re signed in with Google. Choose how your friends will find you.</p>
      <Field
        id="registration-user-id"
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
        id="registration-display-name"
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
      <Field
        id="registration-mobile"
        label="Mobile number"
        hint={`${MOBILE_RULE} Group owners can see your mobile number.`}
        invalid={invalid === "mobile"}
        type="tel"
        value={mobile}
        maxLength={MOBILE_MAX_LENGTH}
        autoComplete="tel"
        onChange={(event) => {
          setMobile(event.target.value);
        }}
      />
      <Button type="submit" variant="primary" busy={busy}>
        Finish registering
      </Button>
      <FeedbackMessage feedback={feedback} />
    </form>
  );
}
