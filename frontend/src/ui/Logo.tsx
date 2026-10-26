/** The Caravan mark: three stops along a winding route. Decorative, beside the product name. */
export function Logo() {
  return (
    <svg className="logo" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect className="logo__tile" width="32" height="32" rx="9" />
      <path
        className="logo__route"
        d="M7 22c4 0 5-6 9-6s5 6 9 6"
        fill="none"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle className="logo__stop" cx="7" cy="22" r="3" />
      <circle className="logo__stop" cx="16" cy="16" r="3" />
      <circle className="logo__stop" cx="25" cy="22" r="3" />
    </svg>
  );
}
