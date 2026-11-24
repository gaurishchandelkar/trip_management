import { useState } from "react";
import { Link } from "react-router";

import { InvalidInputError, type Member, SignedOutError, updateProfile } from "./api";
import { alert, type Feedback, FeedbackMessage, status, UNAVAILABLE } from "./Feedback";
import { Button } from "./ui/Button";
import { Field } from "./ui/Field";
import { Icon } from "./ui/Icon";
import { userIdLabel } from "./ui/PersonDetails";
import { useDocumentTitle } from "./useDocumentTitle";
import {
  DISPLAY_NAME_HINT,
  DISPLAY_NAME_MAX_LENGTH,
  DISPLAY_NAME_RULE,
  isValidDisplayName,
  isValidMobile,
  MOBILE_HINT,
  MOBILE_MAX_LENGTH,
  MOBILE_RULE,
} from "./validation";

/** The signed-in member's own details. The display name and mobile can change; the user ID can't. */
export function Profile({
  member,
  onSaved,
  onSignedOut,
}: {
  member: Member;
  onSaved: (member: Member) => void;
  onSignedOut: () => void;
}) {
  useDocumentTitle("Profile");
  const [displayName, setDisplayName] = useState(member.display_name);
  const [mobile, setMobile] = useState(member.mobile);
  const [invalid, setInvalid] = useState<"display-name" | "mobile" | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);

  function save() {
    const name = displayName.trim();
    const number = mobile.trim();
    if (!isValidDisplayName(name)) {
      setInvalid("display-name");
      setFeedback(alert(DISPLAY_NAME_HINT));
      return;
    }
    if (!isValidMobile(number)) {
      setInvalid("mobile");
      setFeedback(alert(MOBILE_HINT));
      return;
    }
    setInvalid(null);
    setFeedback(null);
    setBusy(true);
    updateProfile(name, number)
      .then((saved) => {
        setBusy(false);
        setDisplayName(saved.display_name);
        setMobile(saved.mobile);
        setFeedback(status("Profile saved."));
        onSaved(saved);
      })
      .catch((error: unknown) => {
        setBusy(false);
        if (error instanceof SignedOutError) onSignedOut();
        else if (error instanceof InvalidInputError)
          setFeedback(alert(`${DISPLAY_NAME_HINT} ${MOBILE_HINT}`));
        else setFeedback(alert(UNAVAILABLE));
      });
  }

  return (
    <div className="profile">
      <Link to="/" className="back-link">
        <Icon name="arrow-left" />
        Back to groups
      </Link>
      <form
        className="card form"
        aria-labelledby="profile-heading"
        onSubmit={(event) => {
          event.preventDefault();
          save();
        }}
      >
        <h2 id="profile-heading">Profile</h2>
        <dl className="profile__fixed">
          <dt>User ID</dt>
          <dd>{userIdLabel(member.user_id)}</dd>
        </dl>
        <Field
          id="profile-display-name"
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
          id="profile-mobile"
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
          Save
        </Button>
        <FeedbackMessage feedback={feedback} />
      </form>
    </div>
  );
}
