import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { getMe, getProviders, SignedOutError, UnavailableError } from "./api";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  getMe: vi.fn(),
  getProviders: vi.fn(),
}));

/** Shows the router's address, so a test can read it. */
function Address() {
  const location = useLocation();
  return <p hidden data-testid="address">{`${location.pathname}${location.search}`}</p>;
}

function address() {
  return screen.getByTestId("address").textContent;
}

function renderSignedOut(path = "/") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <Address />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getMe).mockRejectedValue(new SignedOutError(401));
  vi.mocked(getProviders).mockResolvedValue(["google"]);
});

describe("signed-out screen", () => {
  it("shows Continue with Google and no user ID or password fields", async () => {
    renderSignedOut("/groups/7");

    const google = await screen.findByRole("link", { name: "Continue with Google" });
    expect(google).toHaveAttribute("href", "/api/auth/google/start?return_to=%2Fgroups%2F7");
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(document.querySelector("input")).toBeNull();
    expect(screen.queryByText(/password/i)).toBeNull();
    // The Google mark is drawn inline and hidden from assistive technology.
    const mark = google.querySelector("svg");
    expect(mark).toHaveAttribute("aria-hidden", "true");
    expect(getProviders).toHaveBeenCalledTimes(1);
  });

  it("says sign-in isn't set up when no provider is configured", async () => {
    vi.mocked(getProviders).mockResolvedValue([]);

    renderSignedOut();

    expect(await screen.findByText("Sign-in isn't set up yet. See the README.")).toBeVisible();
    expect(screen.queryByRole("link", { name: "Continue with Google" })).toBeNull();
  });

  it("says something went wrong when the providers can't be loaded", async () => {
    vi.mocked(getProviders).mockRejectedValue(new UnavailableError(503));

    renderSignedOut();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong, please try again.",
    );
  });

  it.each([
    ["failed", "alert", "Couldn't sign in with Google. Please try again."],
    ["cancelled", "status", "Sign-in was cancelled."],
    ["expired", "alert", "Your sign-in expired. Please start again."],
  ])("shows the %s message and removes the query", async (outcome, role, message) => {
    renderSignedOut(`/?sign_in=${outcome}`);

    expect(await screen.findByRole(role)).toHaveTextContent(message);
    await waitFor(() => {
      expect(address()).toBe("/");
    });
    // Removing the query keeps the message.
    await screen.findByRole("link", { name: "Continue with Google" });
    expect(screen.getByRole(role)).toHaveTextContent(message);
  });

  it("ignores an unknown sign-in outcome", async () => {
    renderSignedOut("/?sign_in=constructor");

    await screen.findByRole("link", { name: "Continue with Google" });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
    await waitFor(() => {
      expect(address()).toBe("/");
    });
  });
});
