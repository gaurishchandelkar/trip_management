"""E2E servers: a fresh production build behind `vite preview`, and the backend, on dedicated ports.

Dedicated ports, never reused: a dev server left running must not be what the tests verify.
"""

import http.client
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
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


def _start(name: str, argv: list[str], port: int, health_path: str, log_dir: Path) -> Server:
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
            # Unbuffered, so the log is complete when a hung server times out.
            env={**os.environ, "API_PORT": str(API_PORT), "PYTHONUNBUFFERED": "1"},
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


@pytest.fixture(scope="session")
def servers(tmp_path_factory: pytest.TempPathFactory) -> Iterator[list[Server]]:
    work = tmp_path_factory.mktemp("e2e")
    dist = work / "dist"
    # A fresh build every session, so the tests never drive a stale dist/.
    _build_frontend(dist)
    backend = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", HOST]
    frontend = [_node(), str(VITE), "preview", "frontend", "--outDir", str(dist), "--host", HOST]
    started: list[Server] = []
    try:
        started.append(
            _start("backend", [*backend, "--port", str(API_PORT)], API_PORT, "/api/health", work)
        )
        started.append(
            _start(
                "frontend",
                [*frontend, "--port", str(WEB_PORT), "--strictPort"],
                WEB_PORT,
                "/",
                work,
            )
        )
        yield started
    finally:
        for server in reversed(started):
            server.stop()


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
    foreign = recorder.foreign_origins(base_url)
    if foreign:
        pytest.fail(
            f"The page made requests outside the test servers: {', '.join(foreign)}\n"
            f"{recorder.describe()}",
            pytrace=False,
        )
