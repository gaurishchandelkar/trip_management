"""E2E servers: a fresh production build behind `vite preview`, and the backend, on dedicated ports.

Dedicated ports, never reused: a dev server left running must not be what the tests verify.
"""

import http.client
import os
import secrets
import shutil
import subprocess
import sys
import time
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
from playwright.sync_api import Page

from e2e.network import ApiTraffic

ROOT = Path(__file__).resolve().parent.parent
VITE = ROOT / "node_modules" / "vite" / "bin" / "vite.js"
HOST = "127.0.0.1"
API_PORT = 8100
WEB_PORT = 5273
SCREENSHOT_API_PORT = 8101
SCREENSHOT_WEB_PORT = 5274
FAKE_GOOGLE_PORT = 8102
FAKE_GOOGLE = f"http://{HOST}:{FAKE_GOOGLE_PORT}"
FAKE_GOOGLE_CLIENT_ID = "caravan-e2e"
STARTUP_TIMEOUT_S = 30
BUILD_TIMEOUT_S = 120


@dataclass
class Server:
    name: str
    process: subprocess.Popen[bytes]
    log: Path

    def output(self) -> str:
        return self.log.read_text(errors="replace")[-2000:]

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js isn't on PATH. The E2E tests need it to build and serve the frontend.")
    # Windows also searches the working directory: never run a node planted inside the repo.
    if Path(node).resolve().is_relative_to(ROOT):
        pytest.fail(f"Refusing to run {node}: it's inside the repo, not an installed Node.js.")
    return node


def _responds(port: int, path: str) -> bool:
    connection = http.client.HTTPConnection(HOST, port, timeout=1)
    try:
        connection.request("GET", path)
        return connection.getresponse().status == 200
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def _port_in_use(port: int) -> bool:
    connection = http.client.HTTPConnection(HOST, port, timeout=1)
    try:
        connection.connect()
    except OSError:
        return False
    else:
        return True
    finally:
        connection.close()


def _build_frontend(out_dir: Path) -> None:
    try:
        result = subprocess.run(
            [_node(), str(VITE), "build", "frontend", "--outDir", str(out_dir), "--emptyOutDir"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=BUILD_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"The frontend build didn't finish within {BUILD_TIMEOUT_S} s.", pytrace=False)
    if result.returncode != 0:
        pytest.fail(f"The frontend build failed:\n{result.stdout}{result.stderr}", pytrace=False)


def _start(
    name: str, argv: list[str], port: int, health_path: str, log_dir: Path, env: dict[str, str]
) -> Server:
    if _port_in_use(port):
        pytest.fail(
            f"Port {port} for the {name} server is already in use. Stop whatever is listening "
            "there: the E2E tests never test a server they didn't start.",
            pytrace=False,
        )
    log = log_dir / f"{name}.log"
    with log.open("wb") as out:
        process = subprocess.Popen(
            argv,
            cwd=ROOT,
            stdout=out,
            stderr=subprocess.STDOUT,
            # Unbuffered, so the log is complete when a hung server times out. The caller's env
            # comes last, so a second preview server can proxy to a second backend.
            env={**os.environ, "API_PORT": str(API_PORT), "PYTHONUNBUFFERED": "1", **env},
        )
    server = Server(name, process, log)
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(
                f"The {name} server exited with code {process.returncode} before it was "
                f"healthy:\n{server.output()}",
                pytrace=False,
            )
        if _responds(port, health_path):
            return server
        time.sleep(0.2)
    server.stop()
    pytest.fail(
        f"The {name} server wasn't healthy within {STARTUP_TIMEOUT_S} s:\n{server.output()}",
        pytrace=False,
    )


@dataclass(frozen=True)
class FakeGoogle:
    """The fake provider's server, and the client credentials it was started with."""

    server: Server
    client_secret: str


@contextmanager
def _serve(
    label: str, work: Path, dist: Path, api_port: int, web_port: int, google: FakeGoogle
) -> Generator[list[Server]]:
    """A backend with its own throwaway database, and `vite preview` of `dist` proxying to it.

    The backend signs people in through the fake Google provider, never the real one.
    """
    backend = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", HOST]
    frontend = [_node(), str(VITE), "preview", "frontend", "--outDir", str(dist), "--host", HOST]
    started: list[Server] = []
    try:
        started.append(
            _start(
                f"{label}backend",
                [*backend, "--port", str(api_port)],
                api_port,
                "/api/health",
                work,
                {
                    # A throwaway database, so the tests never touch dev data.
                    "TRIP_DB_PATH": str(work / "trip.db"),
                    "TRIP_GOOGLE_CLIENT_ID": FAKE_GOOGLE_CLIENT_ID,
                    "TRIP_GOOGLE_CLIENT_SECRET": google.client_secret,
                    "TRIP_GOOGLE_ISSUER": FAKE_GOOGLE,
                    # Where the provider sends the browser back: this pair's preview server.
                    "TRIP_PUBLIC_URL": f"http://{HOST}:{web_port}",
                },
            )
        )
        started.append(
            _start(
                f"{label}frontend",
                [*frontend, "--port", str(web_port), "--strictPort"],
                web_port,
                "/",
                work,
                {"API_PORT": str(api_port)},
            )
        )
        yield started
    finally:
        for server in reversed(started):
            server.stop()


@pytest.fixture(scope="session")
def frontend_dist(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dist = tmp_path_factory.mktemp("dist")
    # A fresh build every session, so the tests never drive a stale dist/.
    _build_frontend(dist)
    return dist


@pytest.fixture(scope="session")
def fake_google(tmp_path_factory: pytest.TempPathFactory) -> Iterator[FakeGoogle]:
    """The stand-in for Google (e2e/fake_google.py), shared by both server pairs."""
    # Made per run, so no client secret is ever committed.
    client_secret = secrets.token_urlsafe(24)
    fake = [sys.executable, "-m", "uvicorn", "e2e.fake_google:app", "--host", HOST]
    server = _start(
        "fake-google",
        [*fake, "--port", str(FAKE_GOOGLE_PORT)],
        FAKE_GOOGLE_PORT,
        "/.well-known/openid-configuration",
        tmp_path_factory.mktemp("fake-google"),
        {
            "FAKE_GOOGLE_ISSUER": FAKE_GOOGLE,
            "FAKE_GOOGLE_CLIENT_ID": FAKE_GOOGLE_CLIENT_ID,
            "FAKE_GOOGLE_CLIENT_SECRET": client_secret,
        },
    )
    try:
        yield FakeGoogle(server, client_secret)
    finally:
        server.stop()


@pytest.fixture(scope="session")
def servers(
    tmp_path_factory: pytest.TempPathFactory, frontend_dist: Path, fake_google: FakeGoogle
) -> Iterator[list[Server]]:
    work = tmp_path_factory.mktemp("e2e")
    with _serve("", work, frontend_dist, API_PORT, WEB_PORT, fake_google) as started:
        yield [*started, fake_google.server]


@pytest.fixture(scope="session")
def screenshot_base_url(
    tmp_path_factory: pytest.TempPathFactory, frontend_dist: Path, fake_google: FakeGoogle
) -> Iterator[str]:
    """A second backend and preview server with their own database, for e2e/test_screenshots.py.

    The shared E2E database collects groups from every test, which Browse would show. This one
    holds only the screenshots' sample data, so every run pictures the same screens.
    """
    work = tmp_path_factory.mktemp("screenshots")
    ports = (SCREENSHOT_API_PORT, SCREENSHOT_WEB_PORT)
    with _serve("screenshot-", work, frontend_dist, *ports, fake_google):
        yield f"http://{HOST}:{SCREENSHOT_WEB_PORT}"


@pytest.fixture(scope="session")
def base_url(servers: list[Server]) -> str:
    return f"http://{HOST}:{WEB_PORT}"


@pytest.fixture(autouse=True)
def servers_running(servers: list[Server]) -> None:
    for server in servers:
        if server.process.poll() is not None:
            pytest.fail(
                f"The {server.name} server is not running (exit code "
                f"{server.process.returncode}):\n{server.output()}",
                pytrace=False,
            )


@pytest.fixture(autouse=True)
def traffic(page: Page, base_url: str) -> Iterator[ApiTraffic]:
    recorder = ApiTraffic(page)
    yield recorder
    # The fake Google provider is the one other origin a page may visit: signing in goes there.
    foreign = recorder.foreign_origins(base_url, FAKE_GOOGLE)
    if foreign:
        pytest.fail(
            f"The page made requests outside the test servers: {', '.join(foreign)}\n"
            f"{recorder.describe()}",
            pytrace=False,
        )
