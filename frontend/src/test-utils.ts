import { waitFor } from "@testing-library/react";
import { expect } from "vitest";

/**
 * Waits for the browser tab's title. Screens set it in an effect, which can run after the
 * screen's content is already showing, so a single read right after a `findBy...` can race it.
 */
export async function expectTitle(title: string) {
  await waitFor(() => {
    expect(document.title).toBe(title);
  });
}
