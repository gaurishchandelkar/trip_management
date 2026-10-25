import { useEffect, useState } from "react";

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
import { GroupView } from "./GroupView";
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

const STATUS_TEXT: Record<Group["my_status"], string> = {
  owner: "You own this group",
  member: "You're a member",
  pending: "Request pending",
  none: "",
};

function GroupLine({ group, onOpen }: { group: Group; onOpen: (groupId: number) => void }) {
  return (
    <>
      <button
        type="button"
        className="link"
        onClick={() => {
          onOpen(group.group_id);
        }}
      >
        {group.name}
      </button>{" "}
      <span>
        by {group.owner_display_name}, {group.member_count}{" "}
        {group.member_count === 1 ? "member" : "members"}
      </span>
    </>
  );
}

function MyGroups({
  groups,
  onOpen,
}: {
  groups: Group[] | null;
  onOpen: (groupId: number) => void;
}) {
  return (
    <section aria-labelledby="my-groups-heading">
      <h2 id="my-groups-heading">My groups</h2>
      {groups === null && <p>Loading…</p>}
      {groups?.length === 0 && <p>You aren&apos;t in any groups yet.</p>}
      {groups !== null && groups.length > 0 && (
        <ul>
          {groups.map((group) => (
            <li key={group.group_id}>
              <GroupLine group={group} onOpen={onOpen} />{" "}
              <span>{STATUS_TEXT[group.my_status]}</span>
            </li>
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

  function submit() {
    const trimmed = name.trim();
    if (!isValidGroupName(trimmed)) {
      setFeedback(alert(GROUP_NAME_HINT));
      return;
    }
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
      });
  }

  return (
    <form
      aria-labelledby="create-group-heading"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <h2 id="create-group-heading">Create group</h2>
      <label htmlFor="group-name">Name</label>
      <input
        id="group-name"
        value={name}
        maxLength={GROUP_NAME_MAX_LENGTH}
        onChange={(event) => {
          setName(event.target.value);
        }}
      />
      <label htmlFor="group-description">Description</label>
      <input
        id="group-description"
        value={description}
        maxLength={DESCRIPTION_MAX_LENGTH}
        onChange={(event) => {
          setDescription(event.target.value);
        }}
      />
      <button type="submit">Create group</button>
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

  function submit() {
    const trimmed = name.trim();
    if (!isValidGroupName(trimmed)) {
      setFeedback(alert(GROUP_NAME_HINT));
      return;
    }
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
      });
  }

  return (
    <form
      aria-labelledby="request-heading"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <h2 id="request-heading">Request to join</h2>
      <label htmlFor="request-group-name">Group name</label>
      <input
        id="request-group-name"
        value={name}
        maxLength={GROUP_NAME_MAX_LENGTH}
        onChange={(event) => {
          setName(event.target.value);
        }}
      />
      <button type="submit">Send request</button>
      <FeedbackMessage feedback={feedback} />
    </form>
  );
}

function BrowseGroups({
  groups,
  onSearch,
  onRequest,
  onOpen,
  feedback,
}: {
  groups: Group[] | null;
  onSearch: (search: string) => void;
  onRequest: (group: Group) => void;
  onOpen: (groupId: number) => void;
  feedback: Feedback;
}) {
  const [search, setSearch] = useState("");

  return (
    <section aria-labelledby="browse-heading">
      <h2 id="browse-heading">Browse groups</h2>
      <form
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          onSearch(search.trim());
        }}
      >
        <label htmlFor="browse-search">Search by name</label>
        <input
          id="browse-search"
          value={search}
          maxLength={GROUP_NAME_MAX_LENGTH}
          onChange={(event) => {
            setSearch(event.target.value);
          }}
        />
        <button type="submit">Search</button>
      </form>
      <FeedbackMessage feedback={feedback} />
      {groups === null && <p>Loading…</p>}
      {groups?.length === 0 && <p>No groups found.</p>}
      {groups !== null && groups.length > 0 && (
        <ul>
          {groups.map((group) => (
            <li key={group.group_id}>
              <GroupLine group={group} onOpen={onOpen} />{" "}
              {group.my_status === "none" ? (
                <button
                  type="button"
                  aria-label={`Request to join ${group.name}`}
                  onClick={() => {
                    onRequest(group);
                  }}
                >
                  Request to join
                </button>
              ) : (
                <span>{STATUS_TEXT[group.my_status]}</span>
              )}
            </li>
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
  const [openGroupId, setOpenGroupId] = useState<number | null>(null);
  // Bumped when returning from a group, so the home lists show what changed there.
  const [visit, setVisit] = useState(0);

  function failed(error: unknown) {
    if (error instanceof SignedOutError) onSignedOut();
    else setFeedback(alert(messageFor(error)));
  }

  useEffect(() => {
    const fail = (error: unknown) => {
      if (error instanceof SignedOutError) onSignedOut();
      else setFeedback(alert(messageFor(error)));
    };
    getMyGroups().then(setMyGroups).catch(fail);
    browseGroups().then(setBrowsed).catch(fail);
  }, [onSignedOut, visit]);

  function browse(search: string) {
    if (search !== "" && !isValidGroupName(search)) {
      setFeedback(alert(GROUP_NAME_HINT));
      return;
    }
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

  if (openGroupId !== null) {
    return (
      <GroupView
        groupId={openGroupId}
        onSignedOut={onSignedOut}
        onBack={() => {
          setOpenGroupId(null);
          setVisit((n) => n + 1);
        }}
      />
    );
  }

  return (
    <>
      <MyGroups groups={myGroups} onOpen={setOpenGroupId} />
      <CreateGroupForm
        onSignedOut={onSignedOut}
        onCreated={() => {
          getMyGroups().then(setMyGroups).catch(failed);
        }}
      />
      <RequestByNameForm onRequested={markPending} onSignedOut={onSignedOut} />
      <BrowseGroups
        groups={browsed}
        feedback={feedback}
        onSearch={browse}
        onOpen={setOpenGroupId}
        onRequest={(group) => {
          requestToJoin(group.group_id)
            .then(() => {
              markPending(group.group_id);
            })
            .catch(failed);
        }}
      />
    </>
  );
}
