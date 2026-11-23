import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { getProviders, googleSignInUrl } from "./api";
import { alert, type Feedback, FeedbackMessage, status, UNAVAILABLE } from "./Feedback";
import { GoogleMark } from "./ui/GoogleMark";
import { Skeleton } from "./ui/Skeleton";

type Providers =
  { status: "loading" } | { status: "ready"; google: boolean } | { status: "unavailable" };

/** What the backend's `?sign_in=` redirect means. Anything else shows nothing. */
function signInMessage(value: string | null): Feedback {
  switch (value) {
    case "failed":
      return alert("Couldn't sign in with Google. Please try again.");
    case "cancelled":
      return status("Sign-in was cancelled.");
    case "expired":
      return alert("Your sign-in expired. Please start again.");
    default:
      return null;
  }
}

export function SignedOut() {
  const location = useLocation();
  const navigate = useNavigate();
  const [providers, setProviders] = useState<Providers>({ status: "loading" });
  // Read once: the query is removed from the address straight after.
  const [message] = useState(() =>
    signInMessage(new URLSearchParams(location.search).get("sign_in")),
  );

  useEffect(() => {
    if (new URLSearchParams(location.search).has("sign_in"))
      void navigate({ pathname: location.pathname }, { replace: true });
  }, [location.pathname, location.search, navigate]);

  useEffect(() => {
    getProviders()
      .then((names) => {
        setProviders({ status: "ready", google: names.includes("google") });
      })
      .catch(() => {
        setProviders({ status: "unavailable" });
      });
  }, []);

  return (
    <section className="card form sign-in" aria-labelledby="sign-in-heading">
      <h2 id="sign-in-heading">Sign in</h2>
      <p className="sign-in__body">
        Use your Google account. The first time, you&apos;ll choose a user ID and add your mobile
        number.
      </p>
      {providers.status === "loading" && <Skeleton rows={1} />}
      {providers.status === "ready" && providers.google && (
        <a
          className="button button--secondary sign-in__google"
          href={googleSignInUrl(location.pathname)}
        >
          <GoogleMark />
          Continue with Google
        </a>
      )}
      {providers.status === "ready" && !providers.google && (
        <p className="sign-in__unavailable">Sign-in isn&apos;t set up yet. See the README.</p>
      )}
      {providers.status === "unavailable" && <FeedbackMessage feedback={alert(UNAVAILABLE)} />}
      <FeedbackMessage feedback={message} />
    </section>
  );
}
