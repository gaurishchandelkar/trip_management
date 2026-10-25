import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchGreeting, InvalidNameError } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(response: Response) {
  const fetchMock = vi.fn(() => Promise.resolve(response));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("fetchGreeting", () => {
  it("requests the default greeting without a name", async () => {
    const fetchMock = stubFetch(Response.json({ message: "Hello, World!" }));

    await expect(fetchGreeting()).resolves.toEqual({ message: "Hello, World!" });
    expect(fetchMock).toHaveBeenCalledWith("/api/hello");
  });

  it("sends the name as an encoded query parameter", async () => {
    const fetchMock = stubFetch(Response.json({ message: "Hello, Mary Jane!" }));

    await fetchGreeting("Mary Jane");

    expect(fetchMock).toHaveBeenCalledWith("/api/hello?name=Mary+Jane");
  });

  it("throws InvalidNameError on 422", async () => {
    stubFetch(Response.json({ detail: "Invalid request" }, { status: 422 }));

    await expect(fetchGreeting("<script>")).rejects.toBeInstanceOf(InvalidNameError);
  });

  it("throws when the request fails", async () => {
    stubFetch(new Response(null, { status: 500 }));

    await expect(fetchGreeting()).rejects.toThrow("Request failed: 500");
  });
});
