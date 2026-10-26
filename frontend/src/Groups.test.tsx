import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  approve,
  browseGroups,
  ConflictError,
  createGroup,
  getGroup,
  getMyGroups,
  type Group,
  type GroupDetail,
  InvalidInputError,
  NotFoundError,
  reject,
  requestToJoin,
  requestToJoinByName,
  SignedOutError,
  UnavailableError,
} from "./api";
import { AppRoutes } from "./AppRoutes";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  approve: vi.fn(),
  browseGroups: vi.fn(),
  createGroup: vi.fn(),
  getGroup: vi.fn(),
  getMyGroups: vi.fn(),
  reject: vi.fn(),
  requestToJoin: vi.fn(),
  requestToJoinByName: vi.fn(),
}));

function group(overrides: Partial<Group> = {}): Group {
  return {
    group_id: 1,
    name: "Goa 2027",
    description: "Beach week",
    owner_display_name: "Ada",
    member_count: 1,
    my_status: "none",
    ...overrides,
  };
}

function detail(overrides: Partial<GroupDetail> = {}): GroupDetail {
  return { ...group({ my_status: "owner" }), members: null, pending_requests: null, ...overrides };
}

const PENDING = { request_id: 7, group_id: 1, status: "pending" } as const;
const onSignedOut = vi.fn();

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getMyGroups).mockResolvedValue([]);
  vi.mocked(browseGroups).mockResolvedValue([]);
});

function renderRoutes(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes onSignedOut={onSignedOut} />
    </MemoryRouter>,
  );
}

async function renderGroups() {
  renderRoutes();
  await screen.findByText("You aren't in any groups yet.");
  await screen.findByText("No groups found.");
}

function section(name: string) {
  return screen.getByRole("region", { name });
}

function form(name: string) {
  return screen.getByRole("form", { name });
}

/** Opens a dialog from the home header, whose button comes before any empty-state one. */
async function openDialog(button: "New group" | "Join by name") {
  const [header] = screen.getAllByRole("button", { name: button });
  if (header === undefined) throw new Error(`No ${button} button`);
  await userEvent.click(header);
}

describe("home", () => {
  it("lists my groups and all groups with their status", async () => {
    vi.mocked(getMyGroups).mockResolvedValue([group({ my_status: "owner" })]);
    vi.mocked(browseGroups).mockResolvedValue([
      group({ my_status: "owner" }),
      group({ group_id: 2, name: "Ladakh", owner_display_name: "Bob", member_count: 3 }),
      group({ group_id: 3, name: "Kerala", my_status: "pending" }),
    ]);

    renderRoutes();

    const mine = section("My groups");
    expect(await within(mine).findByRole("link", { name: "Goa 2027" })).toBeInTheDocument();
    expect(within(mine).getByText("You own this group")).toBeInTheDocument();
    const browse = section("Browse groups");
    expect(await within(browse).findByText("by Bob, 3 members")).toBeInTheDocument();
    expect(within(browse).getByRole("button", { name: "Request to join Ladakh" })).toBeEnabled();
    expect(within(browse).getByText("Request pending")).toBeInTheDocument();
    expect(within(browse).queryByRole("button", { name: "Request to join Goa 2027" })).toBeNull();
  });

  it("returns to sign-in when the session is gone", async () => {
    vi.mocked(getMyGroups).mockRejectedValue(new SignedOutError(401));

    renderRoutes();

    await vi.waitFor(() => {
      expect(onSignedOut).toHaveBeenCalled();
    });
  });

  it("shows the unavailable message when loading fails", async () => {
    vi.mocked(browseGroups).mockRejectedValue(new UnavailableError(503));

    renderRoutes();

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
  });
});

describe("creating a group", () => {
  async function create(name: string, description = "") {
    await openDialog("New group");
    await userEvent.type(within(form("Create group")).getByLabelText("Name"), name);
    if (description)
      await userEvent.type(within(form("Create group")).getByLabelText("Description"), description);
    await userEvent.click(
      within(form("Create group")).getByRole("button", { name: "Create group" }),
    );
  }

  it("creates the group and reloads my groups", async () => {
    vi.mocked(createGroup).mockResolvedValue(group({ my_status: "owner" }));
    await renderGroups();
    vi.mocked(getMyGroups).mockResolvedValue([group({ my_status: "owner" })]);

    await create(" Goa 2027 ", "Beach week");

    expect(createGroup).toHaveBeenCalledWith("Goa 2027", "Beach week");
    expect(await screen.findByRole("status")).toHaveTextContent("Created Goa 2027.");
    expect(screen.queryByRole("form", { name: "Create group" })).toBeNull();
    expect(await within(section("My groups")).findByText("Goa 2027")).toBeInTheDocument();
    expect(getMyGroups).toHaveBeenCalledTimes(2);
  });

  it("opens in a dialog with the name field focused", async () => {
    await renderGroups();

    await openDialog("New group");

    expect(screen.getByRole("dialog", { name: "Create group" })).toBeInTheDocument();
    expect(within(form("Create group")).getByLabelText("Name")).toHaveFocus();
  });

  it("sends nothing when cancelled", async () => {
    await renderGroups();
    await openDialog("New group");
    await userEvent.type(within(form("Create group")).getByLabelText("Name"), "Goa");

    await userEvent.click(within(form("Create group")).getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("form", { name: "Create group" })).toBeNull();
    expect(createGroup).not.toHaveBeenCalled();
  });

  it("stays open with the typed name when the name is taken", async () => {
    vi.mocked(createGroup).mockRejectedValue(new ConflictError("group-name-taken"));
    await renderGroups();

    await create("Goa 2027");

    expect(await within(form("Create group")).findByRole("alert")).toHaveTextContent(
      "That group name is already taken.",
    );
    expect(within(form("Create group")).getByLabelText("Name")).toHaveValue("Goa 2027");
    expect(
      within(form("Create group")).getByRole("button", { name: "Create group" }),
    ).toBeEnabled();
  });

  it("opens from the empty My groups state", async () => {
    await renderGroups();

    await userEvent.click(within(section("My groups")).getByRole("button", { name: "New group" }));

    expect(screen.getByRole("form", { name: "Create group" })).toBeInTheDocument();
  });

  it("checks the name before sending", async () => {
    await renderGroups();

    await create("Goa_2027");

    expect(within(form("Create group")).getByRole("alert")).toHaveTextContent("Group names are");
    expect(createGroup).not.toHaveBeenCalled();
  });

  it.each([
    [new ConflictError("group-name-taken"), "That group name is already taken."],
    [new ConflictError("limit-reached"), "Limit reached."],
    [new InvalidInputError(422), "Group names are"],
    [new UnavailableError(503), "Something went wrong"],
  ])("shows a message for %O", async (error, message) => {
    vi.mocked(createGroup).mockRejectedValue(error);
    await renderGroups();

    await create("Goa");

    expect(await within(form("Create group")).findByRole("alert")).toHaveTextContent(message);
  });

  it("returns to sign-in when the session is gone", async () => {
    vi.mocked(createGroup).mockRejectedValue(new SignedOutError(401));
    await renderGroups();

    await create("Goa");

    expect(onSignedOut).toHaveBeenCalled();
  });
});

describe("asking to join", () => {
  async function requestByName(name: string) {
    await openDialog("Join by name");
    await userEvent.type(within(form("Request to join")).getByLabelText("Group name"), name);
    await userEvent.click(
      within(form("Request to join")).getByRole("button", { name: "Send request" }),
    );
  }

  it("asks from the browse list and shows the request as pending", async () => {
    vi.mocked(browseGroups).mockResolvedValue([group()]);
    vi.mocked(requestToJoin).mockResolvedValue(PENDING);
    renderRoutes();

    await userEvent.click(await screen.findByRole("button", { name: "Request to join Goa 2027" }));

    expect(requestToJoin).toHaveBeenCalledWith(1);
    expect(
      await within(section("Browse groups")).findByText("Request pending"),
    ).toBeInTheDocument();
  });

  it.each([
    [new ConflictError("request-pending"), "Request already pending."],
    [new ConflictError("already-member"), "You're already a member."],
  ])("shows a message when asking from the list fails with %O", async (error, message) => {
    vi.mocked(browseGroups).mockResolvedValue([group()]);
    vi.mocked(requestToJoin).mockRejectedValue(error);
    renderRoutes();

    await userEvent.click(await screen.findByRole("button", { name: "Request to join Goa 2027" }));

    expect(await within(section("Browse groups")).findByRole("alert")).toHaveTextContent(message);
  });

  it("asks by name and marks the listed group pending", async () => {
    vi.mocked(browseGroups).mockResolvedValue([group()]);
    vi.mocked(requestToJoinByName).mockResolvedValue(PENDING);
    renderRoutes();
    await screen.findByRole("button", { name: "Request to join Goa 2027" });

    await requestByName(" goa 2027 ");

    expect(requestToJoinByName).toHaveBeenCalledWith("goa 2027");
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Request sent. The owner will decide.",
    );
    expect(screen.queryByRole("form", { name: "Request to join" })).toBeNull();
    expect(within(section("Browse groups")).getByText("Request pending")).toBeInTheDocument();
  });

  it("stays open with the typed name when no group has it", async () => {
    vi.mocked(requestToJoinByName).mockRejectedValue(new NotFoundError(404));
    await renderGroups();

    await requestByName("Nowhere");

    expect(await within(form("Request to join")).findByRole("alert")).toHaveTextContent(
      "No group has that name.",
    );
    expect(within(form("Request to join")).getByLabelText("Group name")).toHaveValue("Nowhere");
  });

  it.each([
    [new NotFoundError(404), "No group has that name."],
    [new ConflictError("limit-reached"), "Limit reached."],
    [new InvalidInputError(422), "Group names are"],
  ])("shows a message when asking by name fails with %O", async (error, message) => {
    vi.mocked(requestToJoinByName).mockRejectedValue(error);
    await renderGroups();

    await requestByName("Nowhere");

    expect(await within(form("Request to join")).findByRole("alert")).toHaveTextContent(message);
  });

  it("checks the name before asking", async () => {
    await renderGroups();

    await requestByName("<script>");

    expect(within(form("Request to join")).getByRole("alert")).toHaveTextContent("Group names are");
    expect(requestToJoinByName).not.toHaveBeenCalled();
  });

  it("returns to sign-in when the session is gone", async () => {
    vi.mocked(requestToJoinByName).mockRejectedValue(new SignedOutError(401));
    await renderGroups();

    await requestByName("Goa");

    expect(onSignedOut).toHaveBeenCalled();
  });
});

describe("searching", () => {
  it("sends the trimmed search term", async () => {
    await renderGroups();
    vi.mocked(browseGroups).mockResolvedValue([group({ name: "Monsoon in Goa" })]);

    await userEvent.type(screen.getByLabelText("Search by name"), " goa ");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(browseGroups).toHaveBeenLastCalledWith("goa");
    expect(await screen.findByRole("link", { name: "Monsoon in Goa" })).toBeInTheDocument();
  });

  it("sends no term for an empty search", async () => {
    await renderGroups();

    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(browseGroups).toHaveBeenLastCalledWith(undefined);
  });

  it("checks the term before searching", async () => {
    await renderGroups();
    vi.mocked(browseGroups).mockClear();

    await userEvent.type(screen.getByLabelText("Search by name"), "100%");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(within(section("Browse groups")).getByRole("alert")).toHaveTextContent(
      "Group names are",
    );
    expect(browseGroups).not.toHaveBeenCalled();
  });

  it("offers to clear a search that found nothing, and reloads the full list", async () => {
    vi.mocked(browseGroups).mockResolvedValue([group()]);
    renderRoutes();
    await screen.findByRole("link", { name: "Goa 2027" });
    vi.mocked(browseGroups).mockResolvedValueOnce([]);
    await userEvent.type(screen.getByLabelText("Search by name"), "Ladakh");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    await screen.findByText("No groups found.");

    await userEvent.click(screen.getByRole("button", { name: "Clear search" }));

    expect(browseGroups).toHaveBeenLastCalledWith(undefined);
    expect(screen.getByLabelText("Search by name")).toHaveValue("");
    expect(await screen.findByRole("link", { name: "Goa 2027" })).toBeInTheDocument();
  });

  it("offers no clear button when nothing was searched", async () => {
    await renderGroups();

    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull();
  });
});

describe("group detail", () => {
  async function open(detailToShow: GroupDetail) {
    vi.mocked(browseGroups).mockResolvedValue([group({ my_status: detailToShow.my_status })]);
    vi.mocked(getGroup).mockResolvedValue(detailToShow);
    renderRoutes();
    await userEvent.click(
      await within(section("Browse groups")).findByRole("link", { name: "Goa 2027" }),
    );
    await screen.findByRole("heading", { name: "Goa 2027" });
  }

  it("shows the owner the members and pending requests", async () => {
    await open(
      detail({
        members: [{ display_name: "Ada" }],
        pending_requests: [{ request_id: 7, display_name: "Bob" }],
      }),
    );

    expect(getGroup).toHaveBeenCalledWith(1);
    expect(screen.getByText("Beach week")).toBeInTheDocument();
    expect(within(section("Members")).getByText("Ada")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve Bob" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject Bob" })).toBeInTheDocument();
  });

  it("shows a non-member only the summary", async () => {
    await open(detail({ my_status: "none" }));

    expect(screen.getByText("Owner: Ada. 1 member.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Members" })).toBeNull();
    expect(screen.queryByRole("region", { name: "Pending requests" })).toBeNull();
  });

  it("says when there are no pending requests", async () => {
    await open(detail({ members: [], pending_requests: [] }));

    expect(screen.getByText("No pending requests.")).toBeInTheDocument();
  });

  it.each([
    ["Approve Bob", approve],
    ["Reject Bob", reject],
  ])("%s calls the API, then reloads the group", async (button, call) => {
    await open(detail({ members: [], pending_requests: [{ request_id: 7, display_name: "Bob" }] }));
    vi.mocked(call).mockResolvedValue({ ...PENDING, status: "approved" });
    vi.mocked(getGroup).mockResolvedValue(detail({ members: [], pending_requests: [] }));

    await userEvent.click(screen.getByRole("button", { name: button }));

    expect(call).toHaveBeenCalledWith(7);
    expect(await screen.findByText("No pending requests.")).toBeInTheDocument();
    expect(getGroup).toHaveBeenCalledTimes(2);
  });

  it("reloads quietly when the request was already decided", async () => {
    await open(detail({ members: [], pending_requests: [{ request_id: 7, display_name: "Bob" }] }));
    vi.mocked(approve).mockRejectedValue(new NotFoundError(404));
    vi.mocked(getGroup).mockResolvedValue(detail({ members: [], pending_requests: [] }));

    await userEvent.click(screen.getByRole("button", { name: "Approve Bob" }));

    expect(await screen.findByText("No pending requests.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it.each([
    [new ConflictError("limit-reached"), "Limit reached."],
    [new UnavailableError(503), "Something went wrong"],
  ])("shows a message when a decision fails with %O", async (error, message) => {
    await open(detail({ members: [], pending_requests: [{ request_id: 7, display_name: "Bob" }] }));
    vi.mocked(approve).mockRejectedValue(error);

    await userEvent.click(screen.getByRole("button", { name: "Approve Bob" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("returns to sign-in when a decision finds the session gone", async () => {
    await open(detail({ members: [], pending_requests: [{ request_id: 7, display_name: "Bob" }] }));
    vi.mocked(reject).mockRejectedValue(new SignedOutError(401));

    await userEvent.click(screen.getByRole("button", { name: "Reject Bob" }));

    await vi.waitFor(() => {
      expect(onSignedOut).toHaveBeenCalled();
    });
  });

  it.each([
    [new NotFoundError(404), "That group no longer exists."],
    [new UnavailableError(503), "Something went wrong"],
  ])("shows a message when loading fails with %O", async (error, message) => {
    vi.mocked(browseGroups).mockResolvedValue([group()]);
    vi.mocked(getGroup).mockRejectedValue(error);
    renderRoutes();

    await userEvent.click(await screen.findByRole("link", { name: "Goa 2027" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("returns to sign-in when loading finds the session gone", async () => {
    vi.mocked(browseGroups).mockResolvedValue([group()]);
    vi.mocked(getGroup).mockRejectedValue(new SignedOutError(401));
    renderRoutes();

    await userEvent.click(await screen.findByRole("link", { name: "Goa 2027" }));

    await vi.waitFor(() => {
      expect(onSignedOut).toHaveBeenCalled();
    });
  });

  it("goes back to the home view and reloads its lists", async () => {
    await open(detail());
    const loadsBefore = vi.mocked(getMyGroups).mock.calls.length;
    const browsesBefore = vi.mocked(browseGroups).mock.calls.length;

    await userEvent.click(screen.getByRole("link", { name: "Back to groups" }));

    expect(await screen.findByRole("region", { name: "My groups" })).toBeInTheDocument();
    expect(getMyGroups).toHaveBeenCalledTimes(loadsBefore + 1);
    expect(browseGroups).toHaveBeenCalledTimes(browsesBefore + 1);
    expect(document.title).toBe("Groups · Caravan");
  });

  it("links each group to its own address and names the tab after it", async () => {
    await open(detail());

    expect(document.title).toBe("Goa 2027 · Caravan");
  });
});

describe("routes", () => {
  it.each(["/groups/abc", "/groups/0", "/groups/-1", "/groups/07", "/groups/99999999999999999999"])(
    "%s is not found, without asking for a group",
    async (path) => {
      renderRoutes(path);

      expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
      expect(getGroup).not.toHaveBeenCalled();
    },
  );

  it("shows page not found for an unknown address, with a link home", async () => {
    renderRoutes("/nowhere");

    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to your groups" })).toHaveAttribute("href", "/");
    expect(document.title).toBe("Page not found · Caravan");
    expect(getMyGroups).not.toHaveBeenCalled();
  });

  it("opens a group straight from its address", async () => {
    vi.mocked(getGroup).mockResolvedValue(detail({ group_id: 42, name: "Ladakh" }));

    renderRoutes("/groups/42");

    expect(await screen.findByRole("heading", { name: "Ladakh" })).toBeInTheDocument();
    expect(getGroup).toHaveBeenCalledWith(42);
    expect(getMyGroups).not.toHaveBeenCalled();
  });

  it("names the tab when the group no longer exists, and links home", async () => {
    vi.mocked(getGroup).mockRejectedValue(new NotFoundError(404));

    renderRoutes("/groups/42");

    expect(await screen.findByRole("alert")).toHaveTextContent("That group no longer exists.");
    expect(screen.getByRole("link", { name: "Back to groups" })).toHaveAttribute("href", "/");
    expect(document.title).toBe("Group not found · Caravan");
  });
});

describe("while a request is in flight", () => {
  // A request that never answers, so the button stays busy for the second click.
  const inFlight = () => new Promise<never>(() => undefined);

  it("sends one create for a double click", async () => {
    vi.mocked(createGroup).mockReturnValue(inFlight());
    await renderGroups();
    await openDialog("New group");
    await userEvent.type(within(form("Create group")).getByLabelText("Name"), "Goa");

    await userEvent.dblClick(
      within(form("Create group")).getByRole("button", { name: "Create group" }),
    );

    expect(createGroup).toHaveBeenCalledTimes(1);
    expect(
      within(form("Create group")).getByRole("button", { name: "Create group" }),
    ).toHaveAttribute("aria-busy", "true");
  });

  it("sends one request by name for a double click", async () => {
    vi.mocked(requestToJoinByName).mockReturnValue(inFlight());
    await renderGroups();
    await openDialog("Join by name");
    await userEvent.type(within(form("Request to join")).getByLabelText("Group name"), "Goa");

    await userEvent.dblClick(
      within(form("Request to join")).getByRole("button", { name: "Send request" }),
    );

    expect(requestToJoinByName).toHaveBeenCalledTimes(1);
  });

  it("sends one request from the list for a double click", async () => {
    vi.mocked(browseGroups).mockResolvedValue([group()]);
    vi.mocked(requestToJoin).mockReturnValue(inFlight());
    renderRoutes();

    await userEvent.dblClick(
      await screen.findByRole("button", { name: "Request to join Goa 2027" }),
    );

    expect(requestToJoin).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Request to join Goa 2027" })).toBeDisabled();
  });

  it("sends one decision for a double click, and holds both buttons", async () => {
    vi.mocked(browseGroups).mockResolvedValue([group({ my_status: "owner" })]);
    vi.mocked(getGroup).mockResolvedValue(
      detail({ members: [], pending_requests: [{ request_id: 7, display_name: "Bob" }] }),
    );
    vi.mocked(approve).mockReturnValue(inFlight());
    renderRoutes();
    await userEvent.click(
      await within(section("Browse groups")).findByRole("link", { name: "Goa 2027" }),
    );

    await userEvent.dblClick(await screen.findByRole("button", { name: "Approve Bob" }));

    expect(approve).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Reject Bob" })).toBeDisabled();
  });
});

describe("marking invalid fields", () => {
  it("marks the group name invalid when its check fails", async () => {
    await renderGroups();
    await openDialog("New group");
    const name = within(form("Create group")).getByLabelText("Name");

    await userEvent.type(name, "Goa_2027");
    await userEvent.click(
      within(form("Create group")).getByRole("button", { name: "Create group" }),
    );

    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(name).toHaveAccessibleDescription(/^Up to 60 letters/);
  });

  it("marks the search term invalid when its check fails", async () => {
    await renderGroups();
    const search = screen.getByLabelText("Search by name");

    await userEvent.type(search, "100%");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(search).toHaveAttribute("aria-invalid", "true");
  });
});

describe("status badges", () => {
  it("shows the member's status on the group screen", async () => {
    vi.mocked(browseGroups).mockResolvedValue([group({ my_status: "member" })]);
    vi.mocked(getGroup).mockResolvedValue(detail({ my_status: "member", members: [] }));
    renderRoutes();

    await userEvent.click(
      await within(section("Browse groups")).findByRole("link", { name: "Goa 2027" }),
    );

    expect(await screen.findByText("You're a member")).toHaveClass("badge--member");
  });

  it("shows an avatar beside each member and requester", async () => {
    vi.mocked(browseGroups).mockResolvedValue([group({ my_status: "owner" })]);
    vi.mocked(getGroup).mockResolvedValue(
      detail({
        members: [{ display_name: "Ada Lovelace" }],
        pending_requests: [{ request_id: 7, display_name: "Bob" }],
      }),
    );
    renderRoutes();

    await userEvent.click(
      await within(section("Browse groups")).findByRole("link", { name: "Goa 2027" }),
    );

    expect(await within(section("Members")).findByText("AL")).toHaveClass("avatar");
    expect(within(section("Pending requests")).getByText("B")).toHaveClass("avatar");
    expect(screen.getByRole("button", { name: "Approve Bob" })).toHaveClass("button--primary");
    expect(screen.getByRole("button", { name: "Reject Bob" })).toHaveClass("button--danger");
  });
});

describe("rendering untrusted text", () => {
  it("shows group names, descriptions and display names with markup as text", async () => {
    const markup = "<img src=x onerror=alert(1)>";
    vi.mocked(browseGroups).mockResolvedValue([
      group({ name: markup, owner_display_name: markup }),
    ]);
    vi.mocked(getGroup).mockResolvedValue(
      detail({
        name: markup,
        description: markup,
        members: [{ display_name: markup }],
        pending_requests: [{ request_id: 7, display_name: markup }],
      }),
    );
    const { container } = renderRoutes();

    await userEvent.click(await screen.findByRole("link", { name: markup }));

    expect(await screen.findByRole("heading", { name: markup })).toBeInTheDocument();
    expect(screen.getAllByText(markup).length).toBeGreaterThanOrEqual(3);
    expect(container.querySelector("img")).toBeNull();
  });
});
