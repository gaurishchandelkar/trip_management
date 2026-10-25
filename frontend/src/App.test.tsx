import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import {
  browseGroups,
  ConflictError,
  getMe,
  getMyGroups,
  InvalidInputError,
  register,
  SignedOutError,
  signIn,
  signOut,
  UnavailableError,
} from "./api";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  browseGroups: vi.fn(),
  getMe: vi.fn(),
  getMyGroups: vi.fn(),
  register: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
}));

const ADA = { user_id: "ada", display_name: "Ada Lovelace" };

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getMyGroups).mockResolvedValue([]);
  vi.mocked(browseGroups).mockResolvedValue([]);
});

async function renderSignedOut() {
  vi.mocked(getMe).mockRejectedValue(new SignedOutError(401));
  render(<App />);
  await screen.findByRole("heading", { name: "Sign in" });
}

function registerForm() {
  return screen.getByRole("form", { name: "Register" });
}

function signInForm() {
  return screen.getByRole("form", { name: "Sign in" });
}

async function fillRegister(userId: string, displayName: string) {
  const form = registerForm();
  await userEvent.type(within(form).getByLabelText("User ID"), userId);
  await userEvent.type(within(form).getByLabelText("Display name"), displayName);
  await userEvent.click(within(form).getByRole("button", { name: "Register" }));
}

async function fillSignIn(userId: string, password: string) {
  const form = signInForm();
  await userEvent.type(within(form).getByLabelText("User ID"), userId);
  if (password) await userEvent.type(within(form).getByLabelText("Password"), password);
  await userEvent.click(within(form).getByRole("button", { name: "Sign in" }));
}

describe("App session", () => {
  it("shows loading, then the sign-in and register forms with labels", async () => {
    vi.mocked(getMe).mockRejectedValue(new SignedOutError(401));

    render(<App />);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(await screen.findByRole("form", { name: "Sign in" })).toBeInTheDocument();
    expect(within(registerForm()).getByLabelText("User ID")).toHaveAttribute("maxLength", "30");
    expect(within(registerForm()).getByLabelText("Display name")).toHaveAttribute(
      "maxLength",
      "50",
    );
  });

  it("uses a password field and says passwords aren't checked yet", async () => {
    await renderSignedOut();

    const password = within(signInForm()).getByLabelText("Password");
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAccessibleDescription("Passwords aren't checked yet.");
  });

  it("goes straight to the signed-in view when a session exists", async () => {
    vi.mocked(getMe).mockResolvedValue(ADA);

    render(<App />);

    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("shows the unavailable message when the session check fails", async () => {
    vi.mocked(getMe).mockRejectedValue(new UnavailableError(503));

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong, please try again.",
    );
  });
});

describe("registering", () => {
  it("registers the trimmed values and says to sign in", async () => {
    vi.mocked(register).mockResolvedValue(ADA);
    await renderSignedOut();

    await fillRegister(" ada ", " Ada Lovelace ");

    expect(register).toHaveBeenCalledWith("ada", "Ada Lovelace");
    expect(await within(registerForm()).findByRole("status")).toHaveTextContent(
      "Registered as ada. You can sign in now.",
    );
  });

  it.each([
    ["1ada", "Ada", "User IDs are 3 to 30"],
    ["ada", "R2D2", "Display names are letters"],
  ])("checks %s / %s before sending", async (userId, displayName, hint) => {
    await renderSignedOut();

    await fillRegister(userId, displayName);

    expect(within(registerForm()).getByRole("alert")).toHaveTextContent(hint);
    expect(register).not.toHaveBeenCalled();
  });

  it.each([
    [new ConflictError("user-id-taken"), "That user ID is already taken."],
    [new InvalidInputError(422), "User IDs are 3 to 30"],
    [new UnavailableError(503), "Something went wrong, please try again."],
  ])("shows a message for %O", async (error, message) => {
    vi.mocked(register).mockRejectedValue(error);
    await renderSignedOut();

    await fillRegister("ada", "Ada");

    expect(await within(registerForm()).findByRole("alert")).toHaveTextContent(message);
  });
});

describe("signing in and out", () => {
  it("signs in and shows the display name", async () => {
    vi.mocked(signIn).mockResolvedValue(ADA);
    await renderSignedOut();

    await fillSignIn("ada", "anything");

    expect(signIn).toHaveBeenCalledWith("ada", "anything");
    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
  });

  it("asks for a user ID and password before sending", async () => {
    await renderSignedOut();

    await fillSignIn("ada", "");

    expect(within(signInForm()).getByRole("alert")).toHaveTextContent(
      "Enter your user ID and a password.",
    );
    expect(signIn).not.toHaveBeenCalled();
  });

  it.each([
    [new SignedOutError(401), "No member has that user ID. Register first."],
    [new InvalidInputError(422), "Enter your user ID and a password."],
    [new UnavailableError(0), "Something went wrong, please try again."],
  ])("shows a message for %O", async (error, message) => {
    vi.mocked(signIn).mockRejectedValue(error);
    await renderSignedOut();

    await fillSignIn("bob", "x");

    expect(await within(signInForm()).findByRole("alert")).toHaveTextContent(message);
  });

  it("signs out and returns to the sign-in form", async () => {
    vi.mocked(getMe).mockResolvedValue(ADA);
    vi.mocked(signOut).mockResolvedValue();
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("form", { name: "Sign in" })).toBeInTheDocument();
  });

  it("returns to the sign-in form when the session already ended", async () => {
    vi.mocked(getMe).mockResolvedValue(ADA);
    vi.mocked(signOut).mockRejectedValue(new SignedOutError(401));
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("form", { name: "Sign in" })).toBeInTheDocument();
  });

  it("stays signed in and shows an alert when sign-out fails", async () => {
    vi.mocked(getMe).mockResolvedValue(ADA);
    vi.mocked(signOut).mockRejectedValue(new UnavailableError(503));
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
  });
});

describe("rendering untrusted text", () => {
  it("shows a display name containing markup as literal text", async () => {
    const markup = "<img src=x onerror=alert(1)>";
    vi.mocked(getMe).mockResolvedValue({ user_id: "eve", display_name: markup });

    const { container } = render(<App />);

    expect(await screen.findByText(markup)).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
  });
});
