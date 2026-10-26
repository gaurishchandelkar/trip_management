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
import { Avatar } from "./ui/Avatar";
import { StatusBadge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Icon } from "./ui/Icon";
import { Skeleton } from "./ui/Skeleton";

interface GroupViewProps {
  groupId: number;
  onBack: () => void;
  onSignedOut: () => void;
}

type Loaded =
  { status: "loading" } | { status: "ready"; group: GroupDetail } | { status: "missing" };

function PendingRequests({
  requests,
  deciding,
  onDecide,
}: {
  requests: PendingRequest[];
  /** The request whose decision is in flight. */
  deciding: number | null;
  onDecide: (decide: (requestId: number) => Promise<JoinRequest>, requestId: number) => void;
}) {
  return (
    <section className="card group__section" aria-labelledby="pending-heading">
      <h3 id="pending-heading">Pending requests</h3>
      {requests.length === 0 ? (
        <p className="empty-state">No pending requests.</p>
      ) : (
        <ul className="people">
          {requests.map((request) => (
            <li key={request.request_id} className="person">
              <Avatar name={request.display_name} />
              <span className="person__name">{request.display_name}</span>
              <span className="person__actions">
                <Button
                  variant="primary"
                  aria-label={`Approve ${request.display_name}`}
                  busy={deciding === request.request_id}
                  onClick={() => {
                    onDecide(approve, request.request_id);
                  }}
                >
                  Approve
                </Button>
                <Button
                  variant="danger"
                  aria-label={`Reject ${request.display_name}`}
                  busy={deciding === request.request_id}
                  onClick={() => {
                    onDecide(reject, request.request_id);
                  }}
                >
                  Reject
                </Button>
              </span>
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
  const [deciding, setDeciding] = useState<number | null>(null);
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
    setDeciding(requestId);
    call(requestId)
      .catch((error: unknown) => {
        if (error instanceof SignedOutError) onSignedOut();
        // Already decided elsewhere: the reload below shows the current state.
        else if (!(error instanceof NotFoundError)) setFeedback(alert(messageFor(error)));
      })
      .finally(() => {
        setDeciding(null);
        setVersion((n) => n + 1);
      });
  }

  return (
    <section className="group" aria-labelledby="group-heading">
      <Button variant="ghost" className="group__back" onClick={onBack}>
        Back to groups
      </Button>
      {loaded.status === "loading" && <Skeleton rows={2} />}
      {loaded.status === "missing" && (
        <FeedbackMessage feedback={alert("That group no longer exists.")} />
      )}
      {loaded.status === "ready" && (
        <>
          <header className="card group__header">
            <div className="group__title">
              <h2 id="group-heading">{loaded.group.name}</h2>
              <StatusBadge status={loaded.group.my_status} />
            </div>
            {loaded.group.description && (
              <p className="group__description">{loaded.group.description}</p>
            )}
            <p className="meta">
              <Icon name="users" />
              <span>
                Owner: {loaded.group.owner_display_name}. {loaded.group.member_count}{" "}
                {loaded.group.member_count === 1 ? "member" : "members"}.
              </span>
            </p>
          </header>
          {loaded.group.members !== null && (
            <section className="card group__section" aria-labelledby="members-heading">
              <h3 id="members-heading">Members</h3>
              <ul className="people">
                {loaded.group.members.map((member, position) => (
                  // Display names can repeat and there's no ID, so the position is the key.
                  <li key={position} className="person">
                    <Avatar name={member.display_name} />
                    <span className="person__name">{member.display_name}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {loaded.group.pending_requests !== null && (
            <PendingRequests
              requests={loaded.group.pending_requests}
              deciding={deciding}
              onDecide={decide}
            />
          )}
        </>
      )}
      <FeedbackMessage feedback={feedback} />
    </section>
  );
}
