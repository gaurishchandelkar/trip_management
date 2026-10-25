import { useCallback, useEffect, useState } from "react";

import { getMe, type Member, SignedOutError, signOut } from "./api";
import { alert, type Feedback, FeedbackMessage, UNAVAILABLE } from "./Feedback";
import { Groups } from "./Groups";
import { SignedOut } from "./SignedOut";

type Session =
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "signed-in"; member: Member }
  | { status: "unavailable" };

function SignedIn({ member, onSignedOut }: { member: Member; onSignedOut: () => void }) {
  const [feedback, setFeedback] = useState<Feedback>(null);

  return (
    <>
      <header>
        <p>
          Signed in as <strong>{member.display_name}</strong>
        </p>
        <button
          type="button"
          onClick={() => {
            signOut()
              .then(onSignedOut)
              .catch((error: unknown) => {
                if (error instanceof SignedOutError) onSignedOut();
                else setFeedback(alert(UNAVAILABLE));
              });
          }}
        >
          Sign out
        </button>
      </header>
      <FeedbackMessage feedback={feedback} />
      <Groups onSignedOut={onSignedOut} />
    </>
  );
}

export function App() {
  const [session, setSession] = useState<Session>({ status: "loading" });

  useEffect(() => {
    getMe()
      .then((member) => {
        setSession({ status: "signed-in", member });
      })
      .catch((error: unknown) => {
        setSession(
          error instanceof SignedOutError ? { status: "signed-out" } : { status: "unavailable" },
        );
      });
  }, []);

  // Stable, because the groups views reload when it changes.
  const signedOut = useCallback(() => {
    setSession({ status: "signed-out" });
  }, []);

  return (
    <main>
      <h1>Trip Management</h1>
      {session.status === "loading" && <p>Loading…</p>}
      {session.status === "unavailable" && <p role="alert">{UNAVAILABLE}</p>}
      {session.status === "signed-out" && (
        <SignedOut
          onSignedIn={(member) => {
            setSession({ status: "signed-in", member });
          }}
        />
      )}
      {session.status === "signed-in" && (
        <SignedIn member={session.member} onSignedOut={signedOut} />
      )}
    </main>
  );
}
