import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.domain.errors import (
    AccountAlreadyLinkedError,
    DomainError,
    IdentityRejectedError,
    LimitReachedError,
    ProviderUnavailableError,
    UnauthenticatedError,
    UserIdTakenError,
)
from backend.domain.models import (
    MAX_OPEN_SIGN_INS,
    MAX_PENDING_PER_ACCOUNT,
    MAX_PENDING_REGISTRATIONS,
    SIGN_IN_LIFETIME,
    Member,
    PendingRegistration,
    SignInFlow,
)
from backend.services import auth, members
from backend.services.auth import (
    Failure,
    NeedsRegistration,
    SignedIn,
    SignInFailed,
    safe_return_to,
)
from backend.storage.store import Store
from backend.tests.integration.fake_provider import FakeIdentityProvider

START = datetime(2027, 1, 1, tzinfo=UTC)
MOBILE = "+919876543210"


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def store(tmp_path: Path) -> Store:
    store = Store(tmp_path / "trip.db")
    store.create_schema()
    return store


@pytest.fixture
def provider() -> FakeIdentityProvider:
    return FakeIdentityProvider()


@pytest.fixture
def clock() -> Clock:
    return Clock()


def begin(
    store: Store, provider: FakeIdentityProvider, clock: Clock, return_to: str | None = None
) -> tuple[str, str]:
    """Starts a sign-in; returns the flow ID (the cookie) and the state (sent to the provider)."""
    started = auth.start_sign_in(store, provider, return_to, clock)
    state = parse_qs(urlsplit(started.redirect_url).query)["state"][0]
    return started.flow_id, state


def finish(
    store: Store,
    provider: FakeIdentityProvider,
    clock: Clock,
    subject: str = "s-ada",
    name: str | None = "Ada Lovelace",
    return_to: str | None = None,
) -> auth.SignInOutcome:
    flow_id, state = begin(store, provider, clock, return_to)
    code = provider.approve(state, subject, name)
    return auth.finish_sign_in(store, provider, flow_id, state, code, None, clock)


def register(store: Store, provider: FakeIdentityProvider, clock: Clock, user_id: str) -> Member:
    outcome = finish(store, provider, clock, subject=f"s-{user_id}")
    assert isinstance(outcome, NeedsRegistration)
    member, _ = auth.complete_registration(
        store, outcome.registration_token, user_id, "Ada", MOBILE, clock
    )
    return member


@pytest.mark.parametrize("path", ["/", "/groups/7", "/groups/7?tab=members", "/a-b_c~%20"])
def test_safe_return_to_keeps_app_paths(path: str) -> None:
    assert safe_return_to(path) == path


@pytest.mark.parametrize(
    "path",
    [
        None,
        "",
        "groups",
        "//evil.example",
        "/\\evil.example",
        "/ok\\evil",
        "/\t/evil.example",
        "/\n/evil.example",
        "/ /evil",
        "https://evil.example",
        "/é",
        "/" + "a" * 200,
    ],
)
def test_safe_return_to_sends_anything_else_home(path: str | None) -> None:
    assert safe_return_to(path) == "/"


def test_new_subject_needs_registration(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    outcome = finish(store, provider, clock, return_to="/groups/2")

    assert isinstance(outcome, NeedsRegistration)
    pending = auth.pending_registration(store, outcome.registration_token, clock)
    assert (pending.subject, pending.suggested_name, pending.return_to) == (
        "s-ada",
        "Ada Lovelace",
        "/groups/2",
    )


def test_registered_subject_is_signed_in(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    ada = register(store, provider, clock, "ada")

    outcome = finish(store, provider, clock, subject="s-ada", return_to="/groups/9")

    assert isinstance(outcome, SignedIn)
    assert outcome.member == ada
    assert outcome.return_to == "/groups/9"
    assert members.current_member(store, outcome.session_token, clock) == ada


def test_a_long_provider_name_is_not_suggested(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    outcome = finish(store, provider, clock, name="A" * 51)

    assert isinstance(outcome, NeedsRegistration)
    assert auth.pending_registration(store, outcome.registration_token, clock).suggested_name == ""


def test_each_start_sends_a_fresh_nonce_and_challenge(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    _, first = begin(store, provider, clock)
    _, second = begin(store, provider, clock)

    assert provider.nonce_for(first) != provider.nonce_for(second)
    assert provider.challenge_for(first) != provider.challenge_for(second)
    assert len(provider.nonce_for(first)) >= 43


def test_one_account_keeps_only_its_newest_pending_registrations(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    tokens: list[str] = []
    for _ in range(MAX_PENDING_PER_ACCOUNT + 2):
        # A second apart, so "newest" is well defined.
        clock.now += timedelta(seconds=1)
        outcome = finish(store, provider, clock, subject="s-new")
        assert isinstance(outcome, NeedsRegistration)
        tokens.append(outcome.registration_token)

    with store.transaction() as tx:
        assert tx.count_pending_registrations() == MAX_PENDING_PER_ACCOUNT
    for token in tokens[-MAX_PENDING_PER_ACCOUNT:]:
        auth.pending_registration(store, token, clock)
    for token in tokens[:-MAX_PENDING_PER_ACCOUNT]:
        with pytest.raises(UnauthenticatedError):
            auth.pending_registration(store, token, clock)


def test_other_accounts_keep_their_pending_registrations(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    other = finish(store, provider, clock, subject="s-other")
    for _ in range(MAX_PENDING_PER_ACCOUNT + 1):
        finish(store, provider, clock, subject="s-new")

    assert isinstance(other, NeedsRegistration)
    auth.pending_registration(store, other.registration_token, clock)


def test_a_flow_is_used_once(store: Store, provider: FakeIdentityProvider, clock: Clock) -> None:
    flow_id, state = begin(store, provider, clock)
    code = provider.approve(state, "s-ada")
    auth.finish_sign_in(store, provider, flow_id, state, code, None, clock)

    again = auth.finish_sign_in(store, provider, flow_id, state, code, None, clock)

    assert again == SignInFailed(Failure.FAILED)


def test_a_flow_expires_after_ten_minutes(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    flow_id, state = begin(store, provider, clock)
    code = provider.approve(state, "s-ada")
    clock.now += SIGN_IN_LIFETIME

    outcome = auth.finish_sign_in(store, provider, flow_id, state, code, None, clock)

    assert outcome == SignInFailed(Failure.FAILED)
    assert provider.exchanges == 0


def test_a_flow_for_another_provider_fails(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    flow_id, state = begin(store, provider, clock)
    code = provider.approve(state, "s-ada")

    other = FakeIdentityProvider(name="other")
    outcome = auth.finish_sign_in(store, other, flow_id, state, code, None, clock)

    assert outcome == SignInFailed(Failure.FAILED)


@pytest.mark.parametrize(
    ("error", "failure"),
    [("access_denied", Failure.CANCELLED), ("server_error", Failure.FAILED)],
)
def test_provider_errors_end_the_flow(
    store: Store, provider: FakeIdentityProvider, clock: Clock, error: str, failure: Failure
) -> None:
    flow_id, state = begin(store, provider, clock)

    outcome = auth.finish_sign_in(store, provider, flow_id, state, None, error, clock)

    assert outcome == SignInFailed(failure)


@pytest.mark.parametrize("failure", [ProviderUnavailableError, IdentityRejectedError])
def test_a_provider_failure_on_exchange_fails(
    store: Store, provider: FakeIdentityProvider, clock: Clock, failure: type[DomainError]
) -> None:
    flow_id, state = begin(store, provider, clock)
    code = provider.approve(state, "s-ada")
    provider.failure = failure

    outcome = auth.finish_sign_in(store, provider, flow_id, state, code, None, clock)

    assert outcome == SignInFailed(Failure.FAILED)


def test_new_subjects_fail_past_the_pending_registration_cap(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    later = START + timedelta(minutes=5)
    with store.transaction() as tx:
        for n in range(MAX_PENDING_REGISTRATIONS):
            tx.add_pending_registration(
                PendingRegistration(f"t{n}", "google", f"s{n}", "", "/", later), keep=1
            )

    assert finish(store, provider, clock) == SignInFailed(Failure.FAILED)


def test_no_flow_cookie_fails(store: Store, provider: FakeIdentityProvider, clock: Clock) -> None:
    _, state = begin(store, provider, clock)

    outcome = auth.finish_sign_in(store, provider, None, state, "code", None, clock)

    assert outcome == SignInFailed(Failure.FAILED)


def test_missing_code_fails(store: Store, provider: FakeIdentityProvider, clock: Clock) -> None:
    flow_id, state = begin(store, provider, clock)

    assert auth.finish_sign_in(store, provider, flow_id, state, None, None, clock) == SignInFailed(
        Failure.FAILED
    )


def test_start_refuses_past_the_cap(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    with store.transaction() as tx:
        for n in range(MAX_OPEN_SIGN_INS):
            later = START + timedelta(minutes=5)
            tx.add_sign_in_flow(SignInFlow(f"f{n}", "google", "s", "n", "v", "/", later))

    with pytest.raises(LimitReachedError):
        auth.start_sign_in(store, provider, None, clock)


def test_start_leaves_no_flow_when_the_provider_is_down(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    provider.failure = ProviderUnavailableError

    with pytest.raises(ProviderUnavailableError):
        auth.start_sign_in(store, provider, None, clock)
    with store.transaction() as tx:
        assert tx.count_sign_in_flows() == 0


def test_registration_links_the_account(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    ada = register(store, provider, clock, "ada")

    with store.transaction() as tx:
        assert tx.member_for_identity("google", "s-ada") == ada
    assert ada == Member(user_id="ada", display_name="Ada", mobile=MOBILE)


def test_a_taken_user_id_keeps_the_pending_registration(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    register(store, provider, clock, "ada")
    outcome = finish(store, provider, clock, subject="s-other")
    assert isinstance(outcome, NeedsRegistration)
    token = outcome.registration_token

    with pytest.raises(UserIdTakenError):
        auth.complete_registration(store, token, "ada", "Ada", MOBILE, clock)
    member, _ = auth.complete_registration(store, token, "ada2", "Ada", MOBILE, clock)

    assert member.user_id == "ada2"


def test_a_pending_registration_is_used_once(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    outcome = finish(store, provider, clock)
    assert isinstance(outcome, NeedsRegistration)
    auth.complete_registration(store, outcome.registration_token, "ada", "Ada", MOBILE, clock)

    with pytest.raises(UnauthenticatedError):
        auth.complete_registration(store, outcome.registration_token, "ada2", "Ada", MOBILE, clock)


@pytest.mark.parametrize("token", [None, "", "unknown"])
def test_registration_needs_a_pending_registration(
    store: Store, clock: Clock, token: str | None
) -> None:
    with pytest.raises(UnauthenticatedError):
        auth.pending_registration(store, token, clock)
    with pytest.raises(UnauthenticatedError):
        auth.complete_registration(store, token, "ada", "Ada", MOBILE, clock)


def test_a_pending_registration_expires_after_ten_minutes(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    outcome = finish(store, provider, clock)
    assert isinstance(outcome, NeedsRegistration)
    clock.now += SIGN_IN_LIFETIME

    with pytest.raises(UnauthenticatedError):
        auth.pending_registration(store, outcome.registration_token, clock)
    with pytest.raises(UnauthenticatedError):
        auth.complete_registration(store, outcome.registration_token, "ada", "Ada", MOBILE, clock)


def test_an_account_links_to_one_member(
    store: Store, provider: FakeIdentityProvider, clock: Clock
) -> None:
    first, second = finish(store, provider, clock), finish(store, provider, clock)
    assert isinstance(first, NeedsRegistration)
    assert isinstance(second, NeedsRegistration)
    auth.complete_registration(store, first.registration_token, "ada", "Ada", MOBILE, clock)

    with pytest.raises(AccountAlreadyLinkedError):
        auth.complete_registration(store, second.registration_token, "ada2", "Ada", MOBILE, clock)


def test_logs_carry_only_the_user_id(
    store: Store, provider: FakeIdentityProvider, clock: Clock, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="backend.services.auth"):
        flow_id, state = begin(store, provider, clock)
        code = provider.approve(state, "s-secret-subject", "Augusta Ada King")
        outcome = auth.finish_sign_in(store, provider, flow_id, state, code, None, clock)
        assert isinstance(outcome, NeedsRegistration)
        auth.complete_registration(
            store, outcome.registration_token, "ada", "Ada Lovelace", MOBILE, clock
        )
        signed_in = finish(store, provider, clock, subject="s-secret-subject")
        assert isinstance(signed_in, SignedIn)
        auth.finish_sign_in(store, provider, "unknown", state, code, None, clock)

    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "sign-in provider=google outcome=needs_registration",
        "registration provider=google outcome=registered user_id=ada",
        "sign-in provider=google outcome=signed_in user_id=ada",
        "sign-in provider=google outcome=failed",
    ]
    logged = "\n".join(messages)
    nonce = provider.nonce_for(state)
    private = [flow_id, state, nonce, code, "s-secret-subject", "Augusta", "Lovelace", MOBILE]
    private += [outcome.registration_token, signed_in.session_token]
    for value in private:
        assert value not in logged
