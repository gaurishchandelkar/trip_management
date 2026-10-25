# Product Spec

A Hello World web app. It exists to show the harness at work, so the product stays deliberately small.

## Backend API

| Method | Path | Response |
|---|---|---|
| GET | `/api/health` | `200 {"status": "ok"}` |
| GET | `/api/hello` | `200 {"message": "Hello, World!"}` |
| GET | `/api/hello?name=Ada` | `200 {"message": "Hello, Ada!"}` |

`name` is optional. It's 1–50 characters of letters from any script, with single spaces, hyphens or apostrophes allowed between letters.
Any invalid request returns `422 {"detail": "Invalid request"}`, and the input is never echoed back.
(Spec: `docs/specs/personalised-greeting.md`.)

## Frontend

- A single page that fetches the default greeting on load.
- It shows "Loading…" while waiting, then the message as the main heading.
- A **Your name** field (at most 50 characters) and a **Greet** button fetch the greeting for the trimmed name.
- An invalid name shows a validation alert, and input is only ever rendered as text.
- If the request fails, it shows an alert that the greeting couldn't be loaded.

## Not in scope

Authentication, persistence, deployment.
