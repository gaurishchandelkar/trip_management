import os


def test_no_trip_setting_reaches_a_test() -> None:
    # backend/tests/conftest.py clears them. Without it, an https TRIP_PUBLIC_URL in the shell
    # made session cookies Secure and the http test client dropped them (docs/HARNESS_LOG.md).
    assert [name for name in os.environ if name.startswith("TRIP_")] == []
