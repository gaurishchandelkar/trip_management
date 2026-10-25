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

export function isValidUserId(value: string): boolean {
  return USER_ID.test(value);
}

export function isValidDisplayName(value: string): boolean {
  return value.length <= DISPLAY_NAME_MAX_LENGTH && DISPLAY_NAME.test(value);
}
