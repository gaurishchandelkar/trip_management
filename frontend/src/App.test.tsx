import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import {
  browseGroups,
  getGroup,
  getMe,
  getMyGroups,
  getProviders,
  type GroupDetail,
  SignedOutError,
  signOut,
  UnavailableError,
} from "./api";
import { expectTitle } from "./test-utils";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  browseGroups: vi.fn(),
  getGroup: vi.fn(),
  getMe: vi.fn(),
  getMyGroups: vi.fn(),
  getProviders: vi.fn(),
  signOut: vi.fn(),
}));

const ADA = { user_id: "ada", display_name: "Ada Lovelace", mobile: "+919876543210" };

function renderApp(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getMyGroups).mockResolvedValue([]);
  vi.mocked(browseGroups).mockResolvedValue([]);
  vi.mocked(getProviders).mockResolvedValue(["google"]);
});

async function renderSignedOut(path = "/") {
  vi.mocked(getMe).mockRejectedValue(new SignedOutError(401));
  renderApp(path);
  await screen.findByRole("heading", { name: "Sign in" });
}

function googleLink() {
  return screen.findByRole("link", { name: "Continue with Google" });
}

describe("App session", () => {
  it("shows loading, then the sign-in screen", async () => {
    vi.mocked(getMe).mockRejectedValue(new SignedOutError(401));

    renderApp();

    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(await googleLink()).toBeInTheDocument();
  });

  it("goes straight to the signed-in view when a session exists", async () => {
    vi.mocked(getMe).mockResolvedValue(ADA);

    renderApp();

    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    expect(getProviders).not.toHaveBeenCalled();
  });

  it("shows the unavailable message when the session check fails", async () => {
    vi.mocked(getMe).mockRejectedValue(new UnavailableError(503));

    renderApp();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong, please try again.",
    );
  });
});

describe("signing out", () => {
  it("signs out and returns to the sign-in screen", async () => {
    vi.mocked(getMe).mockResolvedValue(ADA);
    vi.mocked(signOut).mockResolvedValue();
    renderApp();

    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(await googleLink()).toBeInTheDocument();
  });

  it("returns to the sign-in screen when the session already ended", async () => {
    vi.mocked(getMe).mockResolvedValue(ADA);
    vi.mocked(signOut).mockRejectedValue(new SignedOutError(401));
    renderApp();

    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("stays signed in and shows an alert when sign-out fails", async () => {
    vi.mocked(getMe).mockResolvedValue(ADA);
    vi.mocked(signOut).mockRejectedValue(new UnavailableError(503));
    renderApp();

    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
  });
});

describe("app shell", () => {
  const GROUP: GroupDetail = {
    group_id: 7,
    name: "Goa 2027",
    description: "",
    owner_display_name: "Ada",
    member_count: 1,
    my_status: "owner",
    members: [],
    pending_requests: [],
  };

  it("shows the brand as the page heading, linking home", async () => {
    await renderSignedOut();

    const brand = screen.getByRole("heading", { level: 1, name: "Caravan" });
    expect(within(brand).getByRole("link", { name: "Caravan" })).toHaveAttribute("href", "/");
    await expectTitle("Sign in · Caravan");
  });

  it("moves focus to the main content from the skip link", async () => {
    await renderSignedOut();

    await userEvent.click(screen.getByRole("link", { name: "Skip to content" }));

    expect(screen.getByRole("main")).toHaveFocus();
  });

  it("shows the signed-in member beside their avatar", async () => {
    vi.mocked(getMe).mockResolvedValue(ADA);

    renderApp();

    const banner = screen.getByRole("banner");
    expect(await within(banner).findByText("AL")).toHaveClass("avatar");
    expect(within(banner).getByText("Signed in as")).toHaveTextContent("Signed in as Ada Lovelace");
    await expectTitle("Groups · Caravan");
  });

  it("keeps the address when the session ends, so signing in returns there", async () => {
    vi.mocked(getMe).mockResolvedValue(ADA);
    vi.mocked(getGroup).mockRejectedValueOnce(new SignedOutError(401));
    renderApp("/groups/7");

    expect(await googleLink()).toHaveAttribute(
      "href",
      "/api/auth/google/start?return_to=%2Fgroups%2F7",
    );
    expect(getMyGroups).not.toHaveBeenCalled();
  });

  it("starts at home after an explicit sign-out", async () => {
    vi.mocked(getMe).mockResolvedValue(ADA);
    vi.mocked(getGroup).mockResolvedValue(GROUP);
    vi.mocked(signOut).mockResolvedValue();
    renderApp("/groups/7");
    await screen.findByRole("heading", { level: 2, name: "Goa 2027" });

    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await googleLink()).toHaveAttribute("href", "/api/auth/google/start?return_to=%2F");
    // Home never loaded on the way out.
    expect(getMyGroups).not.toHaveBeenCalled();
    expect(browseGroups).not.toHaveBeenCalled();
  });
});

describe("rendering untrusted text", () => {
  it("shows a display name containing markup as literal text", async () => {
    const markup = "<img src=x onerror=alert(1)>";
    vi.mocked(getMe).mockResolvedValue({ ...ADA, user_id: "eve", display_name: markup });

    const { container } = renderApp();

    expect(await screen.findByText(markup)).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
  });
});
