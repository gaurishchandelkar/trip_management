import logging

import pytest

from backend.api.access_log import ACCESS_LOGGER, RedactAuthQueries, redact_auth_queries
from backend.main import create_app

# uvicorn's own access-log message and argument order (uvicorn/protocols/http/h11_impl.py).
FORMAT = '%s - "%s %s HTTP/%s" %d'
CODE = "4/0AeaYSHB-one-time-code"
STATE = "the-state-value"
CLIENT = "127.0.0.1:5000"


def access_record(path: str) -> logging.LogRecord:
    args = (CLIENT, "GET", path, "1.1", 302)
    return logging.LogRecord(ACCESS_LOGGER, logging.INFO, __file__, 1, FORMAT, args, None)


def test_the_callback_is_logged_without_its_code_or_state() -> None:
    record = access_record(f"/api/auth/google/callback?state={STATE}&code={CODE}&hd=example.com")

    assert RedactAuthQueries().filter(record) is True
    message = record.getMessage()

    assert message == f'{CLIENT} - "GET /api/auth/google/callback HTTP/1.1" 302'
    for leaked in (CODE, STATE, "example.com"):
        assert leaked not in message


def test_other_paths_keep_their_query() -> None:
    record = access_record("/api/groups?q=goa")

    RedactAuthQueries().filter(record)

    assert record.getMessage() == f'{CLIENT} - "GET /api/groups?q=goa HTTP/1.1" 302'


@pytest.mark.parametrize(
    "args",
    # A mapping reaches LogRecord wrapped in a one-element tuple, as logger.info passes it.
    [None, ("only", "three", "args"), ({"path": "/api/auth/google/callback?code=c"},)],
)
def test_records_that_arent_access_lines_pass_untouched(args: tuple[object, ...] | None) -> None:
    record = logging.LogRecord(ACCESS_LOGGER, logging.INFO, __file__, 1, "plain", args, None)
    before = record.args

    assert RedactAuthQueries().filter(record) is True
    assert record.args == before


def test_create_app_redacts_the_access_log(caplog: pytest.LogCaptureFixture) -> None:
    create_app()
    create_app()
    access = logging.getLogger(ACCESS_LOGGER)

    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        path = f"/api/auth/google/callback?state={STATE}&code={CODE}"
        access.info(FORMAT, CLIENT, "GET", path, "1.1", 302)

    assert sum(isinstance(f, RedactAuthQueries) for f in access.filters) == 1
    assert [record.getMessage() for record in caplog.records] == [
        f'{CLIENT} - "GET /api/auth/google/callback HTTP/1.1" 302'
    ]


def test_installing_twice_adds_one_filter() -> None:
    redact_auth_queries()
    redact_auth_queries()

    filters = logging.getLogger(ACCESS_LOGGER).filters
    assert sum(isinstance(f, RedactAuthQueries) for f in filters) == 1
