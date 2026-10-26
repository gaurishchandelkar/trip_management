import { useCallback, useEffect, useState } from "react";

import { getMe, type Member, SignedOutError, signOut } from "./api";
import { alert, type Feedback, FeedbackMessage, UNAVAILABLE } from "./Feedback";
import { Groups } from "./Groups";
import { SignedOut } from "./SignedOut";
import { Avatar } from "./ui/Avatar";
import { Button } from "./ui/Button";
import { Skeleton } from "./ui/Skeleton";

type Session =
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "signed-in"; member: Member }
  | { status: "unavailable" };

function SignedIn({ member, onSignedOut }: { member: Member; onSignedOut: () => void }) {
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);

  return (
    <>
      <header className="session">
        <Avatar name={member.display_name} />
        <p className="session__name">
          Signed in as <strong>{member.display_name}</strong>
        </p>
        <Button
          variant="ghost"
          busy={busy}
          onClick={() => {
            setBusy(true);
            signOut()
              .then(onSignedOut)
              .catch((error: unknown) => {
                setBusy(false);
                if (error instanceof SignedOutError) onSignedOut();
                else setFeedback(alert(UNAVAILABLE));
              });
          }}
        >
          Sign out
        </Button>
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
    <main className="app">
      <h1 className="app__title">Trip Management</h1>
      {session.status === "loading" && <Skeleton rows={2} />}
      {session.status === "unavailable" && <FeedbackMessage feedback={alert(UNAVAILABLE)} />}
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
