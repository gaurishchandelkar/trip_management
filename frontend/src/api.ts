export interface Member {
  user_id: string;
  display_name: string;
}

export class ApiError extends Error {
  constructor(readonly status: number) {
    super(`Request failed: ${String(status)}`);
    this.name = new.target.name;
  }
}

/** 422: the server's validation refused the input. */
export class InvalidInputError extends ApiError {}
/** 401: no session, or sign-in with an unknown user ID. */
export class SignedOutError extends ApiError {}
export class ForbiddenError extends ApiError {}
export class NotFoundError extends ApiError {}
/** 503, any other failure, or the backend couldn't be reached at all. */
export class UnavailableError extends ApiError {}

export type ConflictReason =
  | "user-id-taken"
  | "group-name-taken"
  | "request-pending"
  | "already-member"
  | "limit-reached"
  | "unknown";

// The server's fixed 409 bodies. The UI shows its own text for each, never the server's.
const CONFLICTS: Record<string, ConflictReason> = {
  "User ID already taken": "user-id-taken",
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

export function register(userId: string, displayName: string): Promise<Member> {
  return json("POST", "/api/members", { user_id: userId, display_name: displayName });
}

export function signIn(userId: string, password: string): Promise<Member> {
  return json("POST", "/api/sign-in", { user_id: userId, password });
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

export interface GroupDetail extends Group {
  /** null when the viewer may not see the list. */
  members: Member[] | null;
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
