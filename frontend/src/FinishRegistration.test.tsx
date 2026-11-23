import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import {
  browseGroups,
  completeRegistration,
  ConflictError,
  getGroup,
  getMe,
  getMyGroups,
  getPendingRegistration,
  getProviders,
  InvalidInputError,
  SignedOutError,
  UnavailableError,
} from "./api";
import { expectTitle } from "./test-utils";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  browseGroups: vi.fn(),
  completeRegistration: vi.fn(),
  getGroup: vi.fn(),
  getMe: vi.fn(),
  getMyGroups: vi.fn(),
  getPendingRegistration: vi.fn(),
  getProviders: vi.fn(),
}));

const ADA = { user_id: "ada", display_name: "Ada Lovelace", mobile: "+919876543210" };
/** Shows the router's address, so a test can read it. */
function Address() {
  return (
    <p hidden data-testid="address">
      {useLocation().pathname}
    </p>
  );
}

function address() {
  return screen.getByTestId("address").textContent;
}

async function renderFinish(suggested = "Ada Lovelace", returnTo = "/") {
  vi.mocked(getPendingRegistration).mockResolvedValue({
    display_name: suggested,
    return_to: returnTo,
  });
  render(
    <MemoryRouter initialEntries={["/register/complete"]}>
      <App />
      <Address />
    </MemoryRouter>,
  );
  return screen.findByRole("form", { name: "Finish registering" });
}

async function fill(
  form: HTMLElement,
  values: { userId?: string; name?: string; mobile?: string },
) {
  if (values.userId !== undefined)
    await userEvent.type(within(form).getByLabelText("User ID"), values.userId);
  if (values.name !== undefined) {
    await userEvent.clear(within(form).getByLabelText("Display name"));
    if (values.name) await userEvent.type(within(form).getByLabelText("Display name"), values.name);
  }
  if (values.mobile !== undefined)
    await userEvent.type(within(form).getByLabelText("Mobile number"), values.mobile);
}

function submit(form: HTMLElement) {
  return userEvent.click(within(form).getByRole("button", { name: "Finish registering" }));
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getMe).mockRejectedValue(new SignedOutError(401));
  vi.mocked(getProviders).mockResolvedValue(["google"]);
  vi.mocked(getMyGroups).mockResolvedValue([]);
  vi.mocked(browseGroups).mockResolvedValue([]);
});

describe("finishing registration", () => {
  it("shows three labelled fields, each with its rule", async () => {
    const form = await renderFinish();

    expect(within(form).getByLabelText("User ID")).toHaveAccessibleDescription(
      "3–30 letters, digits, - or _, starting with a letter.",
    );
    expect(within(form).getByLabelText("Display name")).toHaveAccessibleDescription(
      "Up to 50 letters, with single spaces, hyphens or apostrophes.",
    );
    const mobile = within(form).getByLabelText("Mobile number");
    expect(mobile).toHaveAttribute("type", "tel");
    expect(mobile).toHaveAttribute("autocomplete", "tel");
    expect(mobile).toHaveAccessibleDescription(
      "With the country code, for example +91 98765 43210. Group owners can see your mobile number.",
    );
    await expectTitle("Finish registering · Caravan");
    expect(getProviders).not.toHaveBeenCalled();
  });

  it("prefills a valid Google name and leaves an invalid one empty", async () => {
    const form = await renderFinish("Ada Lovelace");
    expect(within(form).getByLabelText("User ID")).toHaveValue("");
    expect(within(form).getByLabelText("Display name")).toHaveValue("Ada Lovelace");
    expect(within(form).getByLabelText("Mobile number")).toHaveValue("");
  });

  it("leaves the name empty when Google's name didn't pass the rule", async () => {
    // The server sends "" for a name that fails the display-name rule.
    const form = await renderFinish("");

    expect(within(form).getByLabelText("Display name")).toHaveValue("");
  });

  it("registers the trimmed values, signs in and lands on the saved address", async () => {
    vi.mocked(completeRegistration).mockResolvedValue(ADA);
    vi.mocked(getGroup).mockResolvedValue({
      group_id: 7,
      name: "Goa 2027",
      description: "",
      owner_display_name: "Bob",
      member_count: 1,
      my_status: "none",
      members: null,
      pending_requests: null,
    });
    const form = await renderFinish("Ada Lovelace", "/groups/7");

    await fill(form, { userId: " ada ", mobile: " +91 98765-43210 " });
    await submit(form);

    expect(completeRegistration).toHaveBeenCalledWith("ada", "Ada Lovelace", "+91 98765-43210");
    expect(await screen.findByRole("heading", { level: 2, name: "Goa 2027" })).toBeVisible();
    expect(address()).toBe("/groups/7");
    expect(screen.getByText("Signed in as")).toHaveTextContent("Signed in as Ada Lovelace");
  });

  it.each([
    ["User ID", { userId: "1ada", mobile: "+919876543210" }, "User IDs are 3 to 30"],
    ["Display name", { userId: "ada", name: "R2D2", mobile: "+919876543210" }, "Display names"],
    ["Mobile number", { userId: "ada", mobile: "98765 43210" }, "with the country code"],
  ])("marks the %s field and sends nothing", async (field, values, hint) => {
    const form = await renderFinish();

    await fill(form, values);
    await submit(form);

    expect(within(form).getByLabelText(field)).toHaveAttribute("aria-invalid", "true");
    expect(within(form).getByRole("alert")).toHaveTextContent(hint);
    expect(completeRegistration).not.toHaveBeenCalled();
  });

  it.each(["09876543210", "+0123456789", "+1234567", "+1234567890123456", "+91 98765 abc", "+"])(
    "shows the mobile hint for %s",
    async (mobile) => {
      const form = await renderFinish();

      await fill(form, { userId: "ada", mobile });
      await submit(form);

      expect(within(form).getByRole("alert")).toHaveTextContent(
        "Enter your mobile number with the country code, for example +91 98765 43210.",
      );
      expect(completeRegistration).not.toHaveBeenCalled();
    },
  );

  it("sends one request on a double click", async () => {
    vi.mocked(completeRegistration).mockReturnValue(new Promise(() => undefined));
    const form = await renderFinish();
    await fill(form, { userId: "ada", mobile: "+919876543210" });

    await userEvent.dblClick(within(form).getByRole("button", { name: "Finish registering" }));

    expect(completeRegistration).toHaveBeenCalledTimes(1);
  });

  it("keeps the input and marks the user ID when it's taken", async () => {
    vi.mocked(completeRegistration).mockRejectedValue(new ConflictError("user-id-taken"));
    const form = await renderFinish();
    await fill(form, { userId: "ada", mobile: "+919876543210" });

    await submit(form);

    expect(await within(form).findByRole("alert")).toHaveTextContent(
      "That user ID is already taken.",
    );
    expect(within(form).getByLabelText("User ID")).toHaveValue("ada");
    expect(within(form).getByLabelText("User ID")).toHaveAttribute("aria-invalid", "true");
    expect(within(form).getByLabelText("Mobile number")).toHaveValue("+919876543210");
    expect(within(form).getByRole("button", { name: "Finish registering" })).toBeEnabled();
  });

  it.each([
    [new ConflictError("account-linked"), "This Google account is already registered."],
    [new InvalidInputError(422), "User IDs are 3 to 30"],
    [new UnavailableError(503), "Something went wrong, please try again."],
  ])("shows a message for %O", async (error, message) => {
    vi.mocked(completeRegistration).mockRejectedValue(error);
    const form = await renderFinish();
    await fill(form, { userId: "ada", mobile: "+919876543210" });

    await submit(form);

    expect(await within(form).findByRole("alert")).toHaveTextContent(message);
  });

  it("returns to sign-in with the expired message on 401", async () => {
    vi.mocked(getPendingRegistration).mockRejectedValue(new SignedOutError(401));
    render(
      <MemoryRouter initialEntries={["/register/complete"]}>
        <App />
        <Address />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your sign-in expired. Please start again.",
    );
    expect(address()).toBe("/");
    expect(await screen.findByRole("link", { name: "Continue with Google" })).toBeVisible();
  });

  it("returns to sign-in when the registration expires while filling in", async () => {
    vi.mocked(completeRegistration).mockRejectedValue(new SignedOutError(401));
    const form = await renderFinish();
    await fill(form, { userId: "ada", mobile: "+919876543210" });

    await submit(form);

    expect(await screen.findByRole("alert")).toHaveTextContent("Your sign-in expired.");
    expect(address()).toBe("/");
  });

  it("says something went wrong when the registration can't be loaded", async () => {
    vi.mocked(getPendingRegistration).mockRejectedValue(new UnavailableError(503));
    render(
      <MemoryRouter initialEntries={["/register/complete"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
  });

  it("renders a suggested name containing markup as text", async () => {
    const markup = "<img src=x onerror=alert(1)>";
    const form = await renderFinish(markup);

    expect(within(form).getByLabelText("Display name")).toHaveValue(markup);
    expect(document.querySelector("img")).toBeNull();
  });
});
