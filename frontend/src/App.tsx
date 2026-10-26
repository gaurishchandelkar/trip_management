import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";

import { getMe, type Member, SignedOutError, signOut } from "./api";
import { AppRoutes } from "./AppRoutes";
import { alert, type Feedback, FeedbackMessage, UNAVAILABLE } from "./Feedback";
import { SignedOut } from "./SignedOut";
import { Avatar } from "./ui/Avatar";
import { Button } from "./ui/Button";
import { Logo } from "./ui/Logo";
import { Skeleton } from "./ui/Skeleton";
import { PRODUCT_NAME, useDocumentTitle } from "./useDocumentTitle";

type Session =
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "signed-in"; member: Member }
  | { status: "unavailable" };

function SessionMenu({ member, onSignedOut }: { member: Member; onSignedOut: () => void }) {
  const navigate = useNavigate();
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);

  // An explicit sign-out starts the next member at home, not on the last group opened here.
  // Signed out first, so the home screen never mounts and loads its lists on the way.
  function signedOut() {
    onSignedOut();
    void navigate("/");
  }

  return (
    <div className="app-header__session">
      <Avatar name={member.display_name} />
      <p className="app-header__name">
        Signed in as <strong>{member.display_name}</strong>
      </p>
      <Button
        variant="ghost"
        busy={busy}
        onClick={() => {
          setBusy(true);
          signOut()
            .then(signedOut)
            .catch((error: unknown) => {
              setBusy(false);
              if (error instanceof SignedOutError) signedOut();
              else setFeedback(alert(UNAVAILABLE));
            });
        }}
      >
        Sign out
      </Button>
      <FeedbackMessage feedback={feedback} />
    </div>
  );
}

function SignInScreen({ onSignedIn }: { onSignedIn: (member: Member) => void }) {
  useDocumentTitle("Sign in");
  return (
    <div className="welcome-layout">
      <section className="welcome" aria-labelledby="welcome-heading">
        <p className="welcome__name">{PRODUCT_NAME}</p>
        <h2 id="welcome-heading" className="welcome__tagline">
          Plan trips together.
        </h2>
        <p className="welcome__body">
          Start a group for your next trip, find your friends&apos; groups, and ask to join. Each
          group&apos;s owner decides who&apos;s in.
        </p>
      </section>
      <SignedOut onSignedIn={onSignedIn} />
    </div>
  );
}

export function App() {
  const [session, setSession] = useState<Session>({ status: "loading" });
  const main = useRef<HTMLElement>(null);

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

  // Stable, because the signed-in screens reload when it changes. Leaves the address alone, so
  // signing in again returns to the screen the session ended on.
  const signedOut = useCallback(() => {
    setSession({ status: "signed-out" });
  }, []);

  return (
    <>
      <a
        href="#main"
        className="skip-link"
        onClick={(event) => {
          event.preventDefault();
          main.current?.focus();
        }}
      >
        Skip to content
      </a>
      <header className="app-header">
        <div className="app-header__inner">
          <h1 className="brand">
            <Link to="/" className="brand__link">
              <Logo />
              {PRODUCT_NAME}
            </Link>
          </h1>
          {session.status === "signed-in" && (
            <SessionMenu member={session.member} onSignedOut={signedOut} />
          )}
        </div>
      </header>
      <main id="main" ref={main} tabIndex={-1} className="app">
        {session.status === "loading" && <Skeleton rows={2} />}
        {session.status === "unavailable" && <FeedbackMessage feedback={alert(UNAVAILABLE)} />}
        {session.status === "signed-out" && (
          <SignInScreen
            onSignedIn={(member) => {
              setSession({ status: "signed-in", member });
            }}
          />
        )}
        {session.status === "signed-in" && <AppRoutes onSignedOut={signedOut} />}
      </main>
    </>
  );
}
