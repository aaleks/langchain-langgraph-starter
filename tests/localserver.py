"""Start the local LangGraph server the one way this project allows -- through
`scripts/serve.sh` -- for a `live` test, and stop it again.

The server starts from a shell a person might have, and not from the suite's
sealed one: the local-only variables removed, then LangSmith switched on with
keys and an endpoint. `serve.sh` must undo all of it; the tests prove it did.
The endpoint is a `.invalid` name (RFC 6761), so a `serve.sh` that stopped
overriding it would be caught by the probe at its lookup, and could deliver
nothing. Two switches keep their local values -- the CLI's analytics and the
version check: their only target is a real third party, so a regression would
be caught here only by letting a request out. The default suite checks that
`serve.sh` exports them (tests/architecture/test_local_only.py). The licence
key is removed and not set: a fake one would send the server to a licence check.
Proxy variables are removed too: a local proxy would turn a request for a
LangSmith host into a connection to 127.0.0.1.

The server runs in a throwaway working copy -- `scripts/serve.sh`,
`langgraph.json` and `src/` -- with `UV_PROJECT` pointing `uv` at this
repository's environment, so its in-memory store (`.langgraph_api/`) is never
the developer's own.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from tests.conftest import LOCAL_ONLY

REPO = Path(__file__).resolve().parents[1]
PROBE = Path(__file__).resolve().parent / "acceptance" / "agents" / "probe"
WINDOWS = sys.platform == "win32"

HOSTILE_ENDPOINT = "http://langsmith-hostile.invalid"
HOSTILE = {
    "LANGSMITH_TRACING": "true",
    "LANGSMITH_TRACING_V2": "true",
    "LANGCHAIN_TRACING_V2": "true",
    "LANGCHAIN_TRACING": "true",
    "LANGSMITH_API_KEY": "lsv2_pt_not_a_real_key",
    "LANGCHAIN_API_KEY": "lsv2_pt_not_a_real_key",
    # Switches the server's usage report on when it is not emptied.
    "LANGSMITH_CONTROL_PLANE_API_KEY": "lsv2_pt_not_a_real_key",
    "LANGSMITH_ENDPOINT": HOSTILE_ENDPOINT,
    "LANGCHAIN_ENDPOINT": HOSTILE_ENDPOINT,
}


# Kept at their local values: a regression in either reaches a real third party.
SPARED = ("LANGGRAPH_CLI_NO_ANALYTICS", "LANGGRAPH_NO_VERSION_CHECK")
PROXIES = {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}


def hostile_environment(base: dict[str, str]) -> dict[str, str]:
    """`base` without the local-only variables or a proxy, then LangSmith
    switched on; the two spared switches at their local values."""
    kept = {k: v for k, v in base.items() if k not in LOCAL_ONLY and k.upper() not in PROXIES}
    return {**kept, **HOSTILE, **{name: LOCAL_ONLY[name] for name in SPARED}}


@dataclass
class LocalServer:
    url: str
    probe_log: Path
    output: Path
    # Set when stopped: True if the signal stopped it, False if it had to be killed.
    stopped_gracefully: bool | None = None

    def records(self) -> list[dict]:
        """What the probe recorded, in every process the server started."""
        if not self.probe_log.is_file():
            return []
        lines = self.probe_log.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]


def bash() -> str:
    """Git for Windows' bash on Windows -- never WSL's, which `System32` puts
    first on a PowerShell PATH and which would run serve.sh in Linux, without
    the probe. Anywhere else, the `bash` on PATH."""
    if not WINDOWS:
        found = shutil.which("bash")
        if found is None:
            raise RuntimeError("bash not found: scripts/serve.sh needs it")
        return found
    git = shutil.which("git")
    if git is not None:
        for parent in Path(git).parents:
            candidate = parent / "bin" / "bash.exe"
            if candidate.is_file():
                return str(candidate)
    raise RuntimeError(
        "Git for Windows' bash not found beside git: scripts/serve.sh needs it, "
        "and WSL's bash (System32) would run it outside this environment"
    )


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


def working_copy(destination: Path) -> Path:
    """What serve.sh serves: itself, langgraph.json, and the graph's source."""
    (destination / "scripts").mkdir(parents=True)
    shutil.copy2(REPO / "scripts" / "serve.sh", destination / "scripts" / "serve.sh")
    shutil.copy2(REPO / "langgraph.json", destination / "langgraph.json")
    shutil.copytree(REPO / "src", destination / "src", ignore=shutil.ignore_patterns("__pycache__"))
    return destination


@contextmanager
def local_server(
    workdir: Path, *, start_timeout: float = 180, settings: Mapping[str, str] | None = None
) -> Iterator[LocalServer]:
    """`settings`: the owner's settings for this server, over the empty ones it
    inherits from the suite -- an Open WebUI, say."""
    copy = working_copy(workdir / "project")
    port = free_port()
    server = LocalServer(
        url=f"http://127.0.0.1:{port}",
        probe_log=workdir / "probe.jsonl",
        output=workdir / "server.log",
    )
    env = {
        **hostile_environment(dict(os.environ)),
        **(settings or {}),
        "UV_PROJECT": str(REPO),
        "PROBE_LOG": str(server.probe_log),
        "PYTHONPATH": os.pathsep.join(filter(None, [str(PROBE), os.environ.get("PYTHONPATH")])),
    }
    with server.output.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [bash(), "scripts/serve.sh", "--port", str(port), "--no-reload"],
            cwd=copy,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            **(
                {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                if WINDOWS
                else {"start_new_session": True}
            ),
        )
        try:
            _await_ok(server, process, start_timeout)
            yield server
        finally:
            server.stopped_gracefully = _stop(process)
    deadline = time.monotonic() + 15
    while port_in_use(port):
        if time.monotonic() > deadline:
            raise RuntimeError(f"the server still holds port {port} after it was stopped")
        time.sleep(0.5)


# No proxy: a configured one would carry a request for 127.0.0.1 off the machine.
_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _await_ok(server: LocalServer, process: subprocess.Popen, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"scripts/serve.sh exited {process.returncode}:\n"
                + server.output.read_text(encoding="utf-8", errors="replace")[-3000:]
            )
        try:
            with _DIRECT.open(server.url + "/ok", timeout=2) as answer:
                if answer.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(
        f"the server did not answer /ok within {timeout}s:\n"
        + server.output.read_text(encoding="utf-8", errors="replace")[-3000:]
    )


def _stop(process: subprocess.Popen, grace: float = 30) -> bool:
    """Stop the whole tree -- bash, uv and the server's Python -- with a signal,
    and say whether that was enough. POSIX: SIGINT to the session, as a person's
    Ctrl+C: uvicorn's lifespan shutdown, then Python's own -- atexit handlers and
    langsmith's flush included. Windows: CTRL_BREAK to the process group, the
    only console event that can target one: the lifespan shutdown runs (measured:
    "Stopping dev persistence flush loop"), but uvicorn re-raises SIGBREAK and
    the process ends without its atexit handlers -- that phase is recorded on
    POSIX only. If the signal cannot be sent (no console) or does not stop it:
    `taskkill /T /F` or SIGKILL to the group, and False."""
    if process.poll() is not None:
        return False
    try:
        if WINDOWS:
            os.kill(process.pid, signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGINT)
        process.wait(timeout=grace)
        return True
    except (OSError, subprocess.TimeoutExpired):
        if process.poll() is not None:
            return False
    if WINDOWS:
        killed = subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, text=True
        )
        if killed.returncode != 0 and process.poll() is None:
            raise RuntimeError(f"taskkill could not stop the server: {killed.stderr.strip()}")
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=grace)
    return False
