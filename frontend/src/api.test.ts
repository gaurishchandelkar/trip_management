import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ConflictError,
  type ConflictReason,
  ForbiddenError,
  getMe,
  InvalidInputError,
  NotFoundError,
  register,
  SignedOutError,
  signIn,
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

const ADA = { user_id: "ada", display_name: "Ada Lovelace" };
const JSON_POST = { method: "POST", headers: { "Content-Type": "application/json" } };

describe("members API", () => {
  it("registers with a JSON body", async () => {
    const fetchMock = stubFetch(Response.json(ADA, { status: 201 }));

    await expect(register("ada", "Ada Lovelace")).resolves.toEqual(ADA);
    expect(fetchMock).toHaveBeenCalledWith("/api/members", {
      ...JSON_POST,
      body: JSON.stringify({ user_id: "ada", display_name: "Ada Lovelace" }),
    });
  });

  it("signs in with the user ID and password", async () => {
    const fetchMock = stubFetch(Response.json(ADA));

    await expect(signIn("ada", "secret")).resolves.toEqual(ADA);
    expect(fetchMock).toHaveBeenCalledWith("/api/sign-in", {
      ...JSON_POST,
      body: JSON.stringify({ user_id: "ada", password: "secret" }),
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
    ["Group name already taken", "group-name-taken"],
    ["Request already pending", "request-pending"],
    ["Already a member", "already-member"],
    ["Limit reached", "limit-reached"],
    ["Something new", "unknown"],
  ])("maps the 409 %s to the reason %s", async (detail, reason) => {
    stubFetch(Response.json({ detail }, { status: 409 }));

    const error: unknown = await register("ada", "Ada").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ConflictError);
    expect(error).toMatchObject({ reason });
  });

  it("treats an unreadable 409 body as an unknown conflict", async () => {
    stubFetch(new Response("not json", { status: 409 }));

    const error: unknown = await register("ada", "Ada").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ConflictError);
    expect((error as ConflictError).reason).toBe("unknown");
  });

  it("treats a 409 body without a string detail as an unknown conflict", async () => {
    stubFetch(Response.json({ detail: 1 }, { status: 409 }));

    const error = (await register("ada", "Ada").catch((e: unknown) => e)) as ConflictError;

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
