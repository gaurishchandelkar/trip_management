import { afterEach, describe, expect, it, vi } from "vitest";

import {
  approve,
  browseGroups,
  completeRegistration,
  ConflictError,
  type ConflictReason,
  createGroup,
  ForbiddenError,
  getGroup,
  getMe,
  getMyGroups,
  getPendingRegistration,
  getProviders,
  googleSignInUrl,
  InvalidInputError,
  NotFoundError,
  reject,
  requestToJoin,
  requestToJoinByName,
  SignedOutError,
  signOut,
  UnavailableError,
} from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(response: Response) {
  const fetchMock = vi.fn(() => Promise.resolve(response));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const ADA = { user_id: "ada", display_name: "Ada Lovelace", mobile: "+919876543210" };

function register() {
  return completeRegistration("ada", "Ada", "+919876543210");
}
const JSON_POST = { method: "POST", headers: { "Content-Type": "application/json" } };

describe("members API", () => {
  it("lists the sign-in providers", async () => {
    const fetchMock = stubFetch(Response.json({ providers: ["google"] }));

    await expect(getProviders()).resolves.toEqual(["google"]);
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/providers", { method: "GET" });
  });

  it("builds the Google sign-in address with an encoded return path", () => {
    expect(googleSignInUrl("/groups/7")).toBe("/api/auth/google/start?return_to=%2Fgroups%2F7");
  });

  it("gets the pending registration", async () => {
    const pending = { display_name: "Ada Lovelace", return_to: "/" };
    const fetchMock = stubFetch(Response.json(pending));

    await expect(getPendingRegistration()).resolves.toEqual(pending);
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/registration", { method: "GET" });
  });

  it("completes the registration with a JSON body", async () => {
    const fetchMock = stubFetch(Response.json(ADA, { status: 201 }));

    await expect(completeRegistration("ada", "Ada Lovelace", "+91 98765 43210")).resolves.toEqual(
      ADA,
    );
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/registration", {
      ...JSON_POST,
      body: JSON.stringify({
        user_id: "ada",
        display_name: "Ada Lovelace",
        mobile: "+91 98765 43210",
      }),
    });
  });

  it("signs out with a bodiless POST", async () => {
    const fetchMock = stubFetch(new Response(null, { status: 204 }));

    await expect(signOut()).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith("/api/sign-out", { method: "POST" });
  });

  it("gets the signed-in member", async () => {
    const fetchMock = stubFetch(Response.json(ADA));

    await expect(getMe()).resolves.toEqual(ADA);
    expect(fetchMock).toHaveBeenCalledWith("/api/me", { method: "GET" });
  });
});

describe("groups API", () => {
  const GROUP = {
    group_id: 1,
    name: "Goa 2027",
    description: "",
    owner_display_name: "Ada",
    member_count: 1,
    my_status: "owner",
  };
  const REQUEST = { request_id: 7, group_id: 1, status: "pending" };

  it("lists my groups", async () => {
    const fetchMock = stubFetch(Response.json([GROUP]));

    await expect(getMyGroups()).resolves.toEqual([GROUP]);
    expect(fetchMock).toHaveBeenCalledWith("/api/me/groups", { method: "GET" });
  });

  it("creates a group with a JSON body", async () => {
    const fetchMock = stubFetch(Response.json(GROUP, { status: 201 }));

    await expect(createGroup("Goa 2027", "Beach")).resolves.toEqual(GROUP);
    expect(fetchMock).toHaveBeenCalledWith("/api/groups", {
      ...JSON_POST,
      body: JSON.stringify({ name: "Goa 2027", description: "Beach" }),
    });
  });

  it("browses without a search term", async () => {
    const fetchMock = stubFetch(Response.json([]));

    await browseGroups();

    expect(fetchMock).toHaveBeenCalledWith("/api/groups", { method: "GET" });
  });

  it("sends the search term as an encoded query parameter", async () => {
    const fetchMock = stubFetch(Response.json([]));

    await browseGroups("Tom & Jerry");

    expect(fetchMock).toHaveBeenCalledWith("/api/groups?q=Tom+%26+Jerry", { method: "GET" });
  });

  it("gets a group by ID", async () => {
    const fetchMock = stubFetch(Response.json({ ...GROUP, members: [], pending_requests: [] }));

    await getGroup(1);

    expect(fetchMock).toHaveBeenCalledWith("/api/groups/1", { method: "GET" });
  });

  it("asks to join from the list with a bodiless POST", async () => {
    const fetchMock = stubFetch(Response.json(REQUEST, { status: 201 }));

    await expect(requestToJoin(1)).resolves.toEqual(REQUEST);
    expect(fetchMock).toHaveBeenCalledWith("/api/groups/1/join-requests", { method: "POST" });
  });

  it("asks to join by name with a JSON body", async () => {
    const fetchMock = stubFetch(Response.json(REQUEST, { status: 201 }));

    await requestToJoinByName("goa 2027");

    expect(fetchMock).toHaveBeenCalledWith("/api/join-requests", {
      ...JSON_POST,
      body: JSON.stringify({ group_name: "goa 2027" }),
    });
  });

  it.each([
    [approve, "approve"],
    [reject, "reject"],
  ])("decides a request with %O", async (decide, path) => {
    const fetchMock = stubFetch(Response.json({ ...REQUEST, status: "approved" }));

    await decide(7);

    expect(fetchMock).toHaveBeenCalledWith(`/api/join-requests/7/${path}`, { method: "POST" });
  });
});

describe("errors", () => {
  it.each([
    [401, SignedOutError],
    [403, ForbiddenError],
    [404, NotFoundError],
    [422, InvalidInputError],
    [500, UnavailableError],
    [503, UnavailableError],
  ])("maps %i to %O", async (status, errorClass) => {
    stubFetch(Response.json({ detail: "x" }, { status }));

    await expect(getMe()).rejects.toBeInstanceOf(errorClass);
  });

  it.each<[string, ConflictReason]>([
    ["User ID already taken", "user-id-taken"],
    ["Account already linked", "account-linked"],
    ["Group name already taken", "group-name-taken"],
    ["Request already pending", "request-pending"],
    ["Already a member", "already-member"],
    ["Limit reached", "limit-reached"],
    ["Something new", "unknown"],
  ])("maps the 409 %s to the reason %s", async (detail, reason) => {
    stubFetch(Response.json({ detail }, { status: 409 }));

    const error: unknown = await register().catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ConflictError);
    expect(error).toMatchObject({ reason });
  });

  it("treats an unreadable 409 body as an unknown conflict", async () => {
    stubFetch(new Response("not json", { status: 409 }));

    const error: unknown = await register().catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ConflictError);
    expect((error as ConflictError).reason).toBe("unknown");
  });

  it("treats a 409 body without a string detail as an unknown conflict", async () => {
    stubFetch(Response.json({ detail: 1 }, { status: 409 }));

    const error = (await register().catch((e: unknown) => e)) as ConflictError;

    expect(error.reason).toBe("unknown");
  });

  it("maps a network failure to UnavailableError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
    );

    await expect(getMe()).rejects.toBeInstanceOf(UnavailableError);
  });

  it("names errors after their class", () => {
    expect(new SignedOutError(401).name).toBe("SignedOutError");
    expect(new ConflictError("limit-reached").message).toBe("Request failed: 409");
  });
});
