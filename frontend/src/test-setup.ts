import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom has HTMLDialogElement but not its methods yet. Open and close it as a browser would,
// without modality; the E2E tests cover focus trapping, Escape and focus return in Chromium.
// Tests in the node environment (theme/tokens.test.ts) have no DOM at all.
if ("HTMLDialogElement" in globalThis) {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
}

afterEach(() => {
  cleanup();
  // jsdom keeps one document per file, so a title left by the last test could pass the next one.
  if ("document" in globalThis) document.title = "";
});
