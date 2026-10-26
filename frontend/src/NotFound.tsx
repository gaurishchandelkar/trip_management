import { Link } from "react-router";

import { useDocumentTitle } from "./useDocumentTitle";

export function NotFound() {
  useDocumentTitle("Page not found");
  return (
    <section className="card not-found" aria-labelledby="not-found-heading">
      <h2 id="not-found-heading">Page not found</h2>
      <p>There&apos;s nothing at this address.</p>
      <Link to="/">Go to your groups</Link>
    </section>
  );
}
