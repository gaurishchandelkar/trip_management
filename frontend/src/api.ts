export interface Member {
  user_id: string;
  display_name: string;
  /** International format, "+" and digits. Only the member and group owners ever see it. */
  mobile: string;
}

/** A Google account with no member yet, waiting for a user ID and mobile number. */
export interface PendingRegistration {
  /** Google's name when it passes the display-name rule, otherwise empty. */
  display_name: string;
  /** The app path to land on once registered. */
  return_to: string;
}

export class ApiError extends Error {
  constructor(readonly status: number) {
    super(`Request failed: ${String(status)}`);
    this.name = new.target.name;
  }
}

/** 422: the server's validation refused the input. */
export class InvalidInputError extends ApiError {}
/** 401: no session, or no usable pending registration. */
export class SignedOutError extends ApiError {}
export class ForbiddenError extends ApiError {}
export class NotFoundError extends ApiError {}
/** 503, any other failure, or the backend couldn't be reached at all. */
export class UnavailableError extends ApiError {}

export type ConflictReason =
  | "user-id-taken"
  | "account-linked"
  | "group-name-taken"
  | "request-pending"
  | "already-member"
  | "limit-reached"
  | "unknown";

// The server's fixed 409 bodies. The UI shows its own text for each, never the server's.
const CONFLICTS: Record<string, ConflictReason> = {
  "User ID already taken": "user-id-taken",
  "Account already linked": "account-linked",
  "Group name already taken": "group-name-taken",
  "Request already pending": "request-pending",
  "Already a member": "already-member",
  "Limit reached": "limit-reached",
};

export class ConflictError extends ApiError {
  constructor(readonly reason: ConflictReason) {
    super(409);
  }
}

async function conflictReason(response: Response): Promise<ConflictReason> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? (CONFLICTS[body.detail] ?? "unknown") : "unknown";
  } catch {
    return "unknown";
  }
}

async function errorFor(response: Response): Promise<ApiError> {
  switch (response.status) {
    case 401:
      return new SignedOutError(401);
    case 403:
      return new ForbiddenError(403);
    case 404:
      return new NotFoundError(404);
    case 409:
      return new ConflictError(await conflictReason(response));
    case 422:
      return new InvalidInputError(422);
    default:
      return new UnavailableError(response.status);
  }
}

async function send(method: "GET" | "POST", path: string, body?: unknown): Promise<Response> {
  const init: RequestInit =
    body === undefined
      ? { method }
      : { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new UnavailableError(0);
  }
  if (!response.ok) throw await errorFor(response);
  return response;
}

async function json<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const response = await send(method, path, body);
  return (await response.json()) as T;
}

/** The providers people can sign in with: `["google"]`, or none when sign-in isn't set up. */
export async function getProviders(): Promise<string[]> {
  const body = await json<{ providers: string[] }>("GET", "/api/auth/providers");
  return body.providers;
}

/**
 * Where the browser goes to sign in with Google. It's a navigation, not a fetch: the backend
 * redirects to Google, and Google sends the browser back to `returnTo` (a path in the app).
 */
export function googleSignInUrl(returnTo: string): string {
  return `/api/auth/google/start?${new URLSearchParams({ return_to: returnTo }).toString()}`;
}

export function getPendingRegistration(): Promise<PendingRegistration> {
  return json("GET", "/api/auth/registration");
}

export function completeRegistration(
  userId: string,
  displayName: string,
  mobile: string,
): Promise<Member> {
  return json("POST", "/api/auth/registration", {
    user_id: userId,
    display_name: displayName,
    mobile,
  });
}

export async function signOut(): Promise<void> {
  await send("POST", "/api/sign-out");
}

export function getMe(): Promise<Member> {
  return json("GET", "/api/me");
}

export type MembershipStatus = "owner" | "member" | "pending" | "none";

export interface Group {
  group_id: number;
  name: string;
  description: string;
  owner_display_name: string;
  member_count: number;
  my_status: MembershipStatus;
}

export interface PendingRequest {
  request_id: number;
  display_name: string;
}

/** Co-members are shown by name only: until passwords are checked, a user ID signs you in. */
export interface GroupMember {
  display_name: string;
}

export interface GroupDetail extends Group {
  /** null when the viewer may not see the list. */
  members: GroupMember[] | null;
  pending_requests: PendingRequest[] | null;
}

export interface JoinRequest {
  request_id: number;
  group_id: number;
  status: "pending" | "approved" | "rejected";
}

export function getMyGroups(): Promise<Group[]> {
  return json("GET", "/api/me/groups");
}

export function createGroup(name: string, description: string): Promise<Group> {
  return json("POST", "/api/groups", { name, description });
}

export function browseGroups(search?: string): Promise<Group[]> {
  const query = search ? `?${new URLSearchParams({ q: search }).toString()}` : "";
  return json("GET", `/api/groups${query}`);
}

export function getGroup(groupId: number): Promise<GroupDetail> {
  return json("GET", `/api/groups/${String(groupId)}`);
}

export function requestToJoin(groupId: number): Promise<JoinRequest> {
  return json("POST", `/api/groups/${String(groupId)}/join-requests`);
}

export function requestToJoinByName(groupName: string): Promise<JoinRequest> {
  return json("POST", "/api/join-requests", { group_name: groupName });
}

export function approve(requestId: number): Promise<JoinRequest> {
  return json("POST", `/api/join-requests/${String(requestId)}/approve`);
}

export function reject(requestId: number): Promise<JoinRequest> {
  return json("POST", `/api/join-requests/${String(requestId)}/reject`);
}
