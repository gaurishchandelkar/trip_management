import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { fetchGreeting, InvalidNameError } from "./api";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  fetchGreeting: vi.fn(),
}));

describe("App", () => {
  it("shows loading, then the default greeting as the heading", async () => {
    vi.mocked(fetchGreeting).mockResolvedValue({ message: "Hello, World!" });

    render(<App />);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Hello, World!" })).toBeInTheDocument();
  });

  it("greets the trimmed name entered in the form", async () => {
    vi.mocked(fetchGreeting).mockImplementation((name) =>
      Promise.resolve({ message: `Hello, ${name ?? "World"}!` }),
    );
    render(<App />);

    await userEvent.type(screen.getByLabelText("Your name"), "  Ada ");
    await userEvent.click(screen.getByRole("button", { name: "Greet" }));

    expect(await screen.findByRole("heading", { name: "Hello, Ada!" })).toBeInTheDocument();
    expect(fetchGreeting).toHaveBeenLastCalledWith("Ada");
  });

  it("limits the name input to 50 characters", () => {
    vi.mocked(fetchGreeting).mockResolvedValue({ message: "Hello, World!" });

    render(<App />);

    expect(screen.getByLabelText("Your name")).toHaveAttribute("maxLength", "50");
  });

  it("shows a validation message for an invalid name", async () => {
    vi.mocked(fetchGreeting).mockRejectedValue(new InvalidNameError());

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Please enter a valid name");
  });

  it("shows an alert when the greeting cannot be loaded", async () => {
    vi.mocked(fetchGreeting).mockRejectedValue(new Error("boom"));

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load greeting");
  });
});
