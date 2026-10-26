import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { alert, FeedbackMessage, status } from "../Feedback";
import { Avatar, initials } from "./Avatar";
import { StatusBadge } from "./Badge";
import { Button } from "./Button";
import { Field } from "./Field";
import { Skeleton } from "./Skeleton";

describe("Button", () => {
  it("is a plain button by default", () => {
    render(<Button>Save</Button>);

    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toBeEnabled();
    expect(button).not.toHaveAttribute("aria-busy");
  });

  it("is disabled and marked busy while its request is in flight", () => {
    render(
      <Button type="submit" variant="primary" busy>
        Save
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveClass("button", "button--primary");
  });
});

describe("Field", () => {
  it("labels the input and ties the hint to it", () => {
    render(<Field id="name" label="Name" hint="Up to 60 characters." />);

    const input = screen.getByLabelText("Name");
    expect(input).toHaveAccessibleDescription("Up to 60 characters.");
    expect(input).not.toHaveAttribute("aria-invalid");
  });

  it("marks the input invalid only when asked", () => {
    render(<Field id="name" label="Name" invalid />);

    const input = screen.getByLabelText("Name");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).not.toHaveAttribute("aria-describedby");
  });
});

describe("Avatar", () => {
  it.each([
    ["Ada Lovelace", "AL"],
    ["Ada", "A"],
    ["  ada   byron lovelace ", "AL"],
    ["Ólafur Arnalds", "ÓA"],
    ["Пётр Чайковский", "ПЧ"],
    ["李 小龍", "李小"],
    ["", ""],
  ])("gives %j the initials %j", (name, expected) => {
    expect(initials(name)).toBe(expected);
  });

  it("is hidden from assistive technology", () => {
    const { container } = render(<Avatar name="Ada Lovelace" />);

    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
    expect(container).toHaveTextContent("AL");
  });
});

describe("StatusBadge", () => {
  it.each([
    ["owner", "You own this group"],
    ["member", "You're a member"],
    ["pending", "Request pending"],
  ] as const)("shows %s as text", (badge, text) => {
    render(<StatusBadge status={badge} />);

    expect(screen.getByText(text)).toHaveClass("badge", `badge--${badge}`);
  });

  it("shows nothing for no status", () => {
    const { container } = render(<StatusBadge status="none" />);

    expect(container).toBeEmptyDOMElement();
  });
});

describe("Skeleton", () => {
  it("tells assistive technology it is loading", () => {
    const { container } = render(<Skeleton rows={4} />);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(container.querySelectorAll(".skeleton")).toHaveLength(4);
  });
});

describe("FeedbackMessage callout", () => {
  it.each([
    [status("Created Goa."), "status"],
    [alert("Limit reached."), "alert"],
  ] as const)("keeps the %j role and text", (feedback, role) => {
    render(<FeedbackMessage feedback={feedback} />);

    const callout = screen.getByRole(role);
    expect(callout).toHaveTextContent(feedback?.text ?? "");
    expect(callout).toHaveClass("callout", `callout--${role}`);
  });

  it("shows nothing without feedback", () => {
    const { container } = render(<FeedbackMessage feedback={null} />);

    expect(container).toBeEmptyDOMElement();
  });
});
