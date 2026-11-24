"""Keeps the sign-in routes' query strings out of uvicorn's access log.

Uvicorn logs each request's path with its query string, so the callback would log Google's
one-time `code` and `state` (spec sso-registration: logs never carry them). The routes under
/api/auth/ are logged by path only.
"""

import logging

ACCESS_LOGGER = "uvicorn.access"
REDACTED_PREFIX = "/api/auth/"
# uvicorn's access record arguments: client address, method, path with query, HTTP version, status.
ACCESS_ARGUMENTS = 5
PATH_ARGUMENT = 2


class RedactAuthQueries(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) == ACCESS_ARGUMENTS:
            path = args[PATH_ARGUMENT]
            if isinstance(path, str) and path.startswith(REDACTED_PREFIX) and "?" in path:
                record.args = (*args[:PATH_ARGUMENT], path.split("?", 1)[0], *args[3:])
        return True


def redact_auth_queries() -> None:
    """Installs the filter on uvicorn's access logger, once however many apps are created."""
    access = logging.getLogger(ACCESS_LOGGER)
    if not any(isinstance(existing, RedactAuthQueries) for existing in access.filters):
        access.addFilter(RedactAuthQueries())
