import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import {
  browseGroups,
  getMe,
  getMyGroups,
  getProviders,
  InvalidInputError,
  SignedOutError,
  UnavailableError,
  updateProfile,
} from "./api";
import { expectTitle } from "./test-utils";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  browseGroups: vi.fn(),
  getMe: vi.fn(),
  getMyGroups: vi.fn(),
  getProviders: vi.fn(),
  updateProfile: vi.fn(),
}));

const ADA = { user_id: "ada", display_name: "Ada Lovelace", mobile: "+919876543210" };

async function renderProfile() {
  vi.mocked(getMe).mockResolvedValue(ADA);
  render(
    <MemoryRouter initialEntries={["/profile"]}>
      <App />
    </MemoryRouter>,
  );
  return screen.findByRole("form", { name: "Profile" });
}

async function replace(form: HTMLElement, label: string, value: string) {
  const field = within(form).getByLabelText(label);
  await userEvent.clear(field);
  if (value) await userEvent.type(field, value);
}

function saveButton(form: HTMLElement) {
  return within(form).getByRole("button", { name: "Save" });
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getMyGroups).mockResolvedValue([]);
  vi.mocked(browseGroups).mockResolvedValue([]);
  vi.mocked(getProviders).mockResolvedValue(["google"]);
});

describe("profile", () => {
  it("shows the user ID as text and fills the current values", async () => {
    const form = await renderProfile();

    expect(within(form).getByText("@ada")).toBeVisible();
    expect(within(form).queryByLabelText("User ID")).toBeNull();
    expect(within(form).getByLabelText("Display name")).toHaveValue("Ada Lovelace");
    const mobile = within(form).getByLabelText("Mobile number");
    expect(mobile).toHaveValue("+919876543210");
    expect(mobile).toHaveAttribute("type", "tel");
    expect(mobile).toHaveAccessibleDescription(
      "With the country code, for example +91 98765 43210. Group owners can see your mobile number.",
    );
    expect(screen.getByRole("link", { name: "Back to groups" })).toHaveAttribute("href", "/");
    await expectTitle("Profile · Caravan");
  });

  it("shows Profile saved and updates the banner", async () => {
    vi.mocked(updateProfile).mockResolvedValue({
      ...ADA,
      display_name: "Augusta",
      mobile: "+447700900123",
    });
    const form = await renderProfile();

    await replace(form, "Display name", " Augusta ");
    await replace(form, "Mobile number", "+44 7700 900123");
    await userEvent.click(saveButton(form));

    expect(updateProfile).toHaveBeenCalledWith("Augusta", "+44 7700 900123");
    expect(await within(form).findByRole("status")).toHaveTextContent("Profile saved.");
    expect(within(form).getByLabelText("Mobile number")).toHaveValue("+447700900123");
    expect(screen.getByText("Signed in as")).toHaveTextContent("Signed in as Augusta");
    expect(saveButton(form)).toBeEnabled();
  });

  it.each([
    ["Display name", "R2D2", "Display names are letters"],
    ["Display name", "", "Display names are letters"],
    ["Mobile number", "98765 43210", "with the country code"],
    ["Mobile number", "+91 abc", "with the country code"],
  ])("refuses %s %j without sending a request", async (label, value, hint) => {
    const form = await renderProfile();

    await replace(form, label, value);
    await userEvent.click(saveButton(form));

    expect(within(form).getByLabelText(label)).toHaveAttribute("aria-invalid", "true");
    expect(within(form).getByRole("alert")).toHaveTextContent(hint);
    expect(within(form).getByLabelText(label)).toHaveValue(value);
    expect(updateProfile).not.toHaveBeenCalled();
  });

  it("a double click sends one request", async () => {
    vi.mocked(updateProfile).mockReturnValue(new Promise(() => undefined));
    const form = await renderProfile();

    await userEvent.dblClick(saveButton(form));

    expect(updateProfile).toHaveBeenCalledTimes(1);
    expect(saveButton(form)).toBeDisabled();
  });

  it.each([
    [new InvalidInputError(422), "Display names are letters"],
    [new UnavailableError(503), "Something went wrong, please try again."],
  ])("keeps the typed text and shows a message for %O", async (error, message) => {
    vi.mocked(updateProfile).mockRejectedValue(error);
    const form = await renderProfile();
    await replace(form, "Mobile number", "+447700900123");

    await userEvent.click(saveButton(form));

    expect(await within(form).findByRole("alert")).toHaveTextContent(message);
    expect(within(form).getByLabelText("Mobile number")).toHaveValue("+447700900123");
    expect(screen.getByText("Signed in as")).toHaveTextContent("Signed in as Ada Lovelace");
  });

  it("returns to sign-in at the same address on 401", async () => {
    vi.mocked(updateProfile).mockRejectedValue(new SignedOutError(401));
    const form = await renderProfile();

    await userEvent.click(saveButton(form));

    expect(await screen.findByRole("link", { name: "Continue with Google" })).toHaveAttribute(
      "href",
      "/api/auth/google/start?return_to=%2Fprofile",
    );
  });
});
