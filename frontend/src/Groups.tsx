import { type ReactNode, useCallback, useEffect, useState } from "react";
import { Link } from "react-router";

import {
  browseGroups,
  createGroup,
  getMyGroups,
  type Group,
  InvalidInputError,
  NotFoundError,
  requestToJoin,
  requestToJoinByName,
  SignedOutError,
} from "./api";
import { alert, type Feedback, FeedbackMessage, messageFor, status } from "./Feedback";
import { StatusBadge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Field } from "./ui/Field";
import { Icon } from "./ui/Icon";
import { Skeleton } from "./ui/Skeleton";
import { useDocumentTitle } from "./useDocumentTitle";
import {
  DESCRIPTION_MAX_LENGTH,
  GROUP_NAME_HINT,
  GROUP_NAME_MAX_LENGTH,
  isValidGroupName,
} from "./validation";

export interface GroupsProps {
  /** Called when a call finds the session gone, so the app can return to sign-in. Keep stable. */
  onSignedOut: () => void;
}

const GROUP_NAME_RULE =
  "Up to 60 letters, digits, spaces and - ' & . , starting with a letter or digit.";

function GroupCard({ group, action }: { group: Group; action?: ReactNode }) {
  return (
    <li className="card group-card">
      <div className="group-card__head">
        <Link to={`/groups/${String(group.group_id)}`} className="group-card__name">
          {group.name}
        </Link>
        <StatusBadge status={group.my_status} />
      </div>
      {group.description && <p className="group-card__description">{group.description}</p>}
      <div className="group-card__foot">
        <p className="meta">
          <Icon name="users" />
          <span>
            by {group.owner_display_name}, {group.member_count}{" "}
            {group.member_count === 1 ? "member" : "members"}
          </span>
        </p>
        {action}
      </div>
    </li>
  );
}

function MyGroups({ groups }: { groups: Group[] | null }) {
  return (
    <section className="home__section" aria-labelledby="my-groups-heading">
      <h2 id="my-groups-heading">My groups</h2>
      {groups === null && <Skeleton rows={2} />}
      {groups?.length === 0 && <p className="empty-state">You aren&apos;t in any groups yet.</p>}
      {groups !== null && groups.length > 0 && (
        <ul className="card-grid">
          {groups.map((group) => (
            <GroupCard key={group.group_id} group={group} />
          ))}
        </ul>
      )}
    </section>
  );
}

function CreateGroupForm({ onCreated, onSignedOut }: { onCreated: () => void } & GroupsProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [invalid, setInvalid] = useState(false);
  const [busy, setBusy] = useState(false);

  function submit() {
    const trimmed = name.trim();
    if (!isValidGroupName(trimmed)) {
      setInvalid(true);
      setFeedback(alert(GROUP_NAME_HINT));
      return;
    }
    setInvalid(false);
    setBusy(true);
    createGroup(trimmed, description.trim())
      .then((group) => {
        setName("");
        setDescription("");
        setFeedback(status(`Created ${group.name}.`));
        onCreated();
      })
      .catch((error: unknown) => {
        if (error instanceof SignedOutError) onSignedOut();
        else if (error instanceof InvalidInputError) setFeedback(alert(GROUP_NAME_HINT));
        else setFeedback(alert(messageFor(error)));
      })
      .finally(() => {
        setBusy(false);
      });
  }

  return (
    <form
      className="card form"
      aria-labelledby="create-group-heading"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <h2 id="create-group-heading">Create group</h2>
      <Field
        id="group-name"
        label="Name"
        hint={GROUP_NAME_RULE}
        invalid={invalid}
        value={name}
        maxLength={GROUP_NAME_MAX_LENGTH}
        onChange={(event) => {
          setName(event.target.value);
        }}
      />
      <Field
        id="group-description"
        label="Description"
        hint="Optional, up to 200 characters."
        value={description}
        maxLength={DESCRIPTION_MAX_LENGTH}
        onChange={(event) => {
          setDescription(event.target.value);
        }}
      />
      <Button type="submit" variant="primary" busy={busy}>
        Create group
      </Button>
      <FeedbackMessage feedback={feedback} />
    </form>
  );
}

function RequestByNameForm({
  onRequested,
  onSignedOut,
}: { onRequested: (groupId: number) => void } & GroupsProps) {
  const [name, setName] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [invalid, setInvalid] = useState(false);
  const [busy, setBusy] = useState(false);

  function submit() {
    const trimmed = name.trim();
    if (!isValidGroupName(trimmed)) {
      setInvalid(true);
      setFeedback(alert(GROUP_NAME_HINT));
      return;
    }
    setInvalid(false);
    setBusy(true);
    requestToJoinByName(trimmed)
      .then((request) => {
        setName("");
        setFeedback(status("Request sent. The owner will decide."));
        onRequested(request.group_id);
      })
      .catch((error: unknown) => {
        if (error instanceof SignedOutError) onSignedOut();
        else if (error instanceof NotFoundError) setFeedback(alert("No group has that name."));
        else if (error instanceof InvalidInputError) setFeedback(alert(GROUP_NAME_HINT));
        else setFeedback(alert(messageFor(error)));
      })
      .finally(() => {
        setBusy(false);
      });
  }

  return (
    <form
      className="card form"
      aria-labelledby="request-heading"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <h2 id="request-heading">Request to join</h2>
      <Field
        id="request-group-name"
        label="Group name"
        hint="The group's exact name. Its owner decides."
        invalid={invalid}
        value={name}
        maxLength={GROUP_NAME_MAX_LENGTH}
        onChange={(event) => {
          setName(event.target.value);
        }}
      />
      <Button type="submit" busy={busy}>
        Send request
      </Button>
      <FeedbackMessage feedback={feedback} />
    </form>
  );
}

function BrowseGroups({
  groups,
  onSearch,
  onRequest,
  requesting,
  invalidSearch,
  feedback,
}: {
  groups: Group[] | null;
  onSearch: (search: string) => void;
  onRequest: (group: Group) => void;
  /** The group whose join request is in flight. */
  requesting: number | null;
  invalidSearch: boolean;
  feedback: Feedback;
}) {
  const [search, setSearch] = useState("");

  return (
    <section className="home__section" aria-labelledby="browse-heading">
      <h2 id="browse-heading">Browse groups</h2>
      <form
        role="search"
        className="search"
        onSubmit={(event) => {
          event.preventDefault();
          onSearch(search.trim());
        }}
      >
        <Field
          id="browse-search"
          label="Search by name"
          invalid={invalidSearch}
          value={search}
          maxLength={GROUP_NAME_MAX_LENGTH}
          onChange={(event) => {
            setSearch(event.target.value);
          }}
        />
        <Button type="submit">
          <Icon name="search" />
          Search
        </Button>
      </form>
      <FeedbackMessage feedback={feedback} />
      {groups === null && <Skeleton />}
      {groups?.length === 0 && <p className="empty-state">No groups found.</p>}
      {groups !== null && groups.length > 0 && (
        <ul className="card-grid">
          {groups.map((group) => (
            <GroupCard
              key={group.group_id}
              group={group}
              action={
                group.my_status === "none" && (
                  <Button
                    variant="primary"
                    aria-label={`Request to join ${group.name}`}
                    busy={requesting === group.group_id}
                    onClick={() => {
                      onRequest(group);
                    }}
                  >
                    Request to join
                  </Button>
                )
              }
            />
          ))}
        </ul>
      )}
    </section>
  );
}

export function Groups({ onSignedOut }: GroupsProps) {
  const [myGroups, setMyGroups] = useState<Group[] | null>(null);
  const [browsed, setBrowsed] = useState<Group[] | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [invalidSearch, setInvalidSearch] = useState(false);
  const [requesting, setRequesting] = useState<number | null>(null);
  useDocumentTitle("Groups");

  const failed = useCallback(
    (error: unknown) => {
      if (error instanceof SignedOutError) onSignedOut();
      else setFeedback(alert(messageFor(error)));
    },
    [onSignedOut],
  );

  // Each visit to the home screen mounts it afresh, so the lists show what changed elsewhere.
  useEffect(() => {
    getMyGroups().then(setMyGroups).catch(failed);
    browseGroups().then(setBrowsed).catch(failed);
  }, [failed]);

  function browse(search: string) {
    if (search !== "" && !isValidGroupName(search)) {
      setInvalidSearch(true);
      setFeedback(alert(GROUP_NAME_HINT));
      return;
    }
    setInvalidSearch(false);
    setFeedback(null);
    browseGroups(search || undefined)
      .then(setBrowsed)
      .catch(failed);
  }

  function markPending(groupId: number) {
    setBrowsed(
      (groups) =>
        groups?.map((g) => (g.group_id === groupId ? { ...g, my_status: "pending" } : g)) ?? null,
    );
  }

  return (
    <div className="home">
      <MyGroups groups={myGroups} />
      <div className="home__forms">
        <CreateGroupForm
          onSignedOut={onSignedOut}
          onCreated={() => {
            getMyGroups().then(setMyGroups).catch(failed);
          }}
        />
        <RequestByNameForm onRequested={markPending} onSignedOut={onSignedOut} />
      </div>
      <BrowseGroups
        groups={browsed}
        feedback={feedback}
        requesting={requesting}
        invalidSearch={invalidSearch}
        onSearch={browse}
        onRequest={(group) => {
          setRequesting(group.group_id);
          requestToJoin(group.group_id)
            .then(() => {
              markPending(group.group_id);
            })
            .catch(failed)
            .finally(() => {
              setRequesting(null);
            });
        }}
      />
    </div>
  );
}
