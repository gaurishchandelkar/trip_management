import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
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
import { Dialog } from "./ui/Dialog";
import { EmptyState } from "./ui/EmptyState";
import { Field } from "./ui/Field";
import { Icon } from "./ui/Icon";
import { Skeleton } from "./ui/Skeleton";
import { useDocumentTitle } from "./useDocumentTitle";
import {
  DESCRIPTION_MAX_LENGTH,
  GROUP_NAME_HINT,
  GROUP_NAME_MAX_LENGTH,
  GROUP_NAME_RULE,
  isValidGroupName,
  JOIN_BY_NAME_RULE,
  SEARCH_RULE,
} from "./validation";

export interface GroupsProps {
  /** Called when a call finds the session gone, so the app can return to sign-in. Keep stable. */
  onSignedOut: () => void;
}

type OpenDialog = "create" | "join" | null;

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

function MyGroups({ groups, onCreate }: { groups: Group[] | null; onCreate: () => void }) {
  return (
    <section className="home__section" aria-labelledby="my-groups-heading">
      <h3 id="my-groups-heading">My groups</h3>
      {groups === null && <Skeleton rows={2} />}
      {groups?.length === 0 && (
        <EmptyState
          message="You aren't in any groups yet."
          action={
            <Button variant="primary" onClick={onCreate}>
              <Icon name="plus" />
              New group
            </Button>
          }
        />
      )}
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

function CreateGroupForm({
  onCreated,
  onCancel,
  onSignedOut,
}: { onCreated: (group: Group) => void; onCancel: () => void } & GroupsProps) {
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
      .then(onCreated)
      .catch((error: unknown) => {
        setBusy(false);
        if (error instanceof SignedOutError) onSignedOut();
        else if (error instanceof InvalidInputError) setFeedback(alert(GROUP_NAME_HINT));
        else setFeedback(alert(messageFor(error)));
      });
  }

  return (
    <form
      className="form"
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
      <FeedbackMessage feedback={feedback} />
      <div className="form__actions">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" busy={busy}>
          Create group
        </Button>
      </div>
    </form>
  );
}

function RequestByNameForm({
  onRequested,
  onCancel,
  onSignedOut,
}: { onRequested: (groupId: number) => void; onCancel: () => void } & GroupsProps) {
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
        onRequested(request.group_id);
      })
      .catch((error: unknown) => {
        setBusy(false);
        if (error instanceof SignedOutError) onSignedOut();
        else if (error instanceof NotFoundError) setFeedback(alert("No group has that name."));
        else if (error instanceof InvalidInputError) setFeedback(alert(GROUP_NAME_HINT));
        else setFeedback(alert(messageFor(error)));
      });
  }

  return (
    <form
      className="form"
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
        hint={JOIN_BY_NAME_RULE}
        invalid={invalid}
        value={name}
        maxLength={GROUP_NAME_MAX_LENGTH}
        onChange={(event) => {
          setName(event.target.value);
        }}
      />
      <FeedbackMessage feedback={feedback} />
      <div className="form__actions">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" busy={busy}>
          Send request
        </Button>
      </div>
    </form>
  );
}

function BrowseGroups({
  groups,
  onSearch,
  onRequest,
  requesting,
  searching,
  invalidSearch,
  feedback,
}: {
  groups: Group[] | null;
  /** Returns whether the search was sent: a term that fails its check isn't. */
  onSearch: (search: string) => boolean;
  onRequest: (group: Group) => void;
  /** The group whose join request is in flight. */
  requesting: number | null;
  /** A search is in flight. */
  searching: boolean;
  invalidSearch: boolean;
  feedback: Feedback;
}) {
  const [search, setSearch] = useState("");
  // The term the list was filtered by, so an empty result can offer to clear it.
  const [searched, setSearched] = useState("");

  function searchFor(term: string) {
    if (onSearch(term)) setSearched(term);
  }

  return (
    <section className="home__section" aria-labelledby="browse-heading">
      <h3 id="browse-heading">Browse groups</h3>
      <form
        role="search"
        className="search"
        onSubmit={(event) => {
          event.preventDefault();
          searchFor(search.trim());
        }}
      >
        <Field
          id="browse-search"
          label="Search by name"
          hint={SEARCH_RULE}
          invalid={invalidSearch}
          value={search}
          maxLength={GROUP_NAME_MAX_LENGTH}
          onChange={(event) => {
            setSearch(event.target.value);
          }}
        />
        <Button type="submit" busy={searching}>
          <Icon name="search" />
          Search
        </Button>
      </form>
      <FeedbackMessage feedback={feedback} />
      {groups === null && <Skeleton />}
      {groups?.length === 0 && (
        <EmptyState
          message="No groups found."
          action={
            searched !== "" && (
              <Button
                busy={searching}
                onClick={() => {
                  setSearch("");
                  searchFor("");
                }}
              >
                Clear search
              </Button>
            )
          }
        />
      )}
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
  // The outcome of a dialog, shown on the home screen once the dialog closes.
  const [notice, setNotice] = useState<Feedback>(null);
  const [dialog, setDialog] = useState<OpenDialog>(null);
  const [invalidSearch, setInvalidSearch] = useState(false);
  const [requesting, setRequesting] = useState<number | null>(null);
  const [searching, setSearching] = useState(false);
  const newGroupButton = useRef<HTMLButtonElement>(null);
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

  function browse(search: string): boolean {
    if (search !== "" && !isValidGroupName(search)) {
      setInvalidSearch(true);
      setFeedback(alert(GROUP_NAME_HINT));
      return false;
    }
    setInvalidSearch(false);
    setFeedback(null);
    setSearching(true);
    browseGroups(search || undefined)
      .then(setBrowsed)
      .catch(failed)
      .finally(() => {
        setSearching(false);
      });
    return true;
  }

  function markPending(groupId: number) {
    setBrowsed(
      (groups) =>
        groups?.map((g) => (g.group_id === groupId ? { ...g, my_status: "pending" } : g)) ?? null,
    );
  }

  function open(which: Exclude<OpenDialog, null>) {
    setNotice(null);
    setDialog(which);
  }

  function close() {
    setDialog(null);
  }

  return (
    <div className="home">
      <div className="home__header">
        <h2>Groups</h2>
        <div className="home__actions">
          <Button
            onClick={() => {
              open("join");
            }}
          >
            Join by name
          </Button>
          <Button
            ref={newGroupButton}
            variant="primary"
            onClick={() => {
              open("create");
            }}
          >
            <Icon name="plus" />
            New group
          </Button>
        </div>
      </div>
      <FeedbackMessage feedback={notice} />
      <MyGroups
        groups={myGroups}
        onCreate={() => {
          // The dialog returns focus to whatever had it when it opened. The empty state's
          // button disappears once the group exists, so focus the header's New group instead.
          newGroupButton.current?.focus();
          open("create");
        }}
      />
      <BrowseGroups
        groups={browsed}
        feedback={feedback}
        requesting={requesting}
        searching={searching}
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
              // Only if no other group's request has started since.
              setRequesting((current) => (current === group.group_id ? null : current));
            });
        }}
      />
      <Dialog open={dialog === "create"} onClose={close} labelledBy="create-group-heading">
        <CreateGroupForm
          onSignedOut={onSignedOut}
          onCancel={close}
          onCreated={(group) => {
            close();
            setNotice(status(`Created ${group.name}.`));
            getMyGroups().then(setMyGroups).catch(failed);
          }}
        />
      </Dialog>
      <Dialog open={dialog === "join"} onClose={close} labelledBy="request-heading">
        <RequestByNameForm
          onSignedOut={onSignedOut}
          onCancel={close}
          onRequested={(groupId) => {
            close();
            setNotice(status("Request sent. The owner will decide."));
            markPending(groupId);
          }}
        />
      </Dialog>
    </div>
  );
}
