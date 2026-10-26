// Mirrors the server's rules so the UI can say which field is wrong. The server stays the control.

export const USER_ID_MAX_LENGTH = 30;
export const DISPLAY_NAME_MAX_LENGTH = 50;
export const PASSWORD_MAX_LENGTH = 128;

const USER_ID = /^[A-Za-z][A-Za-z0-9_-]{2,29}$/;
const DISPLAY_NAME = /^\p{L}+(?:[ '-]\p{L}+)*$/u;

export const USER_ID_HINT =
  "User IDs are 3 to 30 letters, digits, hyphens or underscores, starting with a letter.";
export const DISPLAY_NAME_HINT =
  "Display names are letters with single spaces, hyphens or apostrophes, up to 50 characters.";

// Each field's rule, shown under it before the member can fail it.
export const USER_ID_RULE = "3–30 letters, digits, - or _, starting with a letter.";
export const DISPLAY_NAME_RULE = "Up to 50 letters, with single spaces, hyphens or apostrophes.";

export function isValidUserId(value: string): boolean {
  return USER_ID.test(value);
}

export function isValidDisplayName(value: string): boolean {
  return value.length <= DISPLAY_NAME_MAX_LENGTH && DISPLAY_NAME.test(value);
}

export const GROUP_NAME_MAX_LENGTH = 60;
export const DESCRIPTION_MAX_LENGTH = 200;

const GROUP_NAME = /^[\p{L}\p{N}][\p{L}\p{N}\-'&., ]*$/u;

export const GROUP_NAME_HINT =
  "Group names are up to 60 letters, digits, spaces and - ' & . , starting with a letter or digit, with single spaces.";

export const GROUP_NAME_RULE =
  "Up to 60 letters, digits, spaces and - ' & . , starting with a letter or digit, with single spaces.";
export const JOIN_BY_NAME_RULE = "The group's full name. Capitals don't matter. Its owner decides.";
export const SEARCH_RULE = "Part of a group's name: letters, digits, spaces and - ' & . ,";

export function isValidGroupName(value: string): boolean {
  return (
    value.length <= GROUP_NAME_MAX_LENGTH &&
    GROUP_NAME.test(value) &&
    !value.endsWith(" ") &&
    !value.includes("  ")
  );
}
