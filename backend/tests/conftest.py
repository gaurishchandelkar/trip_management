import os

import pytest


@pytest.fixture(autouse=True)
def no_trip_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clears every TRIP_* variable, so a developer's shell can't change what a test sees.

    create_app reads TRIP_DB_PATH, TRIP_PUBLIC_URL and the Google settings. A test that needs
    one sets it with monkeypatch.
    """
    for name in [name for name in os.environ if name.startswith("TRIP_")]:
        monkeypatch.delenv(name)
