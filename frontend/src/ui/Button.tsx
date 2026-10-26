import type { ComponentProps } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ComponentProps<"button"> {
  variant?: ButtonVariant;
  /** A request is in flight: the button is disabled, so a second click sends nothing. */
  busy?: boolean;
}

export function Button({
  variant = "secondary",
  busy = false,
  disabled = false,
  type = "button",
  className,
  ...rest
}: ButtonProps) {
  const classes = ["button", `button--${variant}`, className].filter(Boolean).join(" ");
  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      {...rest}
    />
  );
}
