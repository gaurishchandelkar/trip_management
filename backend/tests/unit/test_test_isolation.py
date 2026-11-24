import os
from collections.abc import Iterator

import pytest


@pytest.fixture(scope="module")
def trip_setting_in_shell() -> Iterator[None]:
    # Module scope runs before the function-scoped autouse fixture in backend/tests/conftest.py,
    # so this stands in for a developer's shell and that fixture has to remove it.
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("TRIP_PUBLIC_URL", "https://trips.example.org")
        yield


def test_no_trip_setting_reaches_a_test(trip_setting_in_shell: None) -> None:
    # Without the fixture, an https TRIP_PUBLIC_URL in the shell made session cookies Secure
    # and the http test client dropped them (docs/HARNESS_LOG.md).
    assert [name for name in os.environ if name.startswith("TRIP_")] == []
