import { useEffect, useState } from "react";

import {
  approve,
  getGroup,
  type GroupDetail,
  type JoinRequest,
  NotFoundError,
  type PendingRequest,
  reject,
  SignedOutError,
} from "./api";
import { alert, type Feedback, FeedbackMessage, messageFor } from "./Feedback";

interface GroupViewProps {
  groupId: number;
  onBack: () => void;
  onSignedOut: () => void;
}

type Loaded =
  { status: "loading" } | { status: "ready"; group: GroupDetail } | { status: "missing" };

function PendingRequests({
  requests,
  onDecide,
}: {
  requests: PendingRequest[];
  onDecide: (decide: (requestId: number) => Promise<JoinRequest>, requestId: number) => void;
}) {
  return (
    <section aria-labelledby="pending-heading">
      <h3 id="pending-heading">Pending requests</h3>
      {requests.length === 0 ? (
        <p>No pending requests.</p>
      ) : (
        <ul>
          {requests.map((request) => (
            <li key={request.request_id}>
              {request.display_name}{" "}
              <button
                type="button"
                aria-label={`Approve ${request.display_name}`}
                onClick={() => {
                  onDecide(approve, request.request_id);
                }}
              >
                Approve
              </button>{" "}
              <button
                type="button"
                aria-label={`Reject ${request.display_name}`}
                onClick={() => {
                  onDecide(reject, request.request_id);
                }}
              >
                Reject
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function GroupView({ groupId, onBack, onSignedOut }: GroupViewProps) {
  const [loaded, setLoaded] = useState<Loaded>({ status: "loading" });
  const [feedback, setFeedback] = useState<Feedback>(null);
  // Bumped after each decision, to reload the group with its new members and requests.
  const [version, setVersion] = useState(0);

  useEffect(() => {
    getGroup(groupId)
      .then((group) => {
        setLoaded({ status: "ready", group });
      })
      .catch((error: unknown) => {
        if (error instanceof SignedOutError) onSignedOut();
        else if (error instanceof NotFoundError) setLoaded({ status: "missing" });
        else setFeedback(alert(messageFor(error)));
      });
  }, [groupId, onSignedOut, version]);

  function decide(call: (requestId: number) => Promise<JoinRequest>, requestId: number) {
    setFeedback(null);
    call(requestId)
      .catch((error: unknown) => {
        if (error instanceof SignedOutError) onSignedOut();
        // Already decided elsewhere: the reload below shows the current state.
        else if (!(error instanceof NotFoundError)) setFeedback(alert(messageFor(error)));
      })
      .finally(() => {
        setVersion((n) => n + 1);
      });
  }

  return (
    <section aria-labelledby="group-heading">
      <button type="button" onClick={onBack}>
        Back to groups
      </button>
      {loaded.status === "loading" && <p>Loading…</p>}
      {loaded.status === "missing" && <p role="alert">That group no longer exists.</p>}
      {loaded.status === "ready" && (
        <>
          <h2 id="group-heading">{loaded.group.name}</h2>
          {loaded.group.description && <p>{loaded.group.description}</p>}
          <p>
            Owner: {loaded.group.owner_display_name}. {loaded.group.member_count}{" "}
            {loaded.group.member_count === 1 ? "member" : "members"}.
          </p>
          {loaded.group.members !== null && (
            <section aria-labelledby="members-heading">
              <h3 id="members-heading">Members</h3>
              <ul>
                {loaded.group.members.map((member) => (
                  <li key={member.user_id}>{member.display_name}</li>
                ))}
              </ul>
            </section>
          )}
          {loaded.group.pending_requests !== null && (
            <PendingRequests requests={loaded.group.pending_requests} onDecide={decide} />
          )}
        </>
      )}
      <FeedbackMessage feedback={feedback} />
    </section>
  );
}
