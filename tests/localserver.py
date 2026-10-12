"""Start the local LangGraph server the one way this project allows -- through
`scripts/serve.sh` -- for a `live` test, and stop it again.

The server is started from a shell a person might have: LangSmith tracing
switched on and a key exported, over the suite's sealed environment. It is
`scripts/serve.sh`'s job to make that harmless; the tests prove it did.
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
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROBE = Path(__file__).resolve().parent / "acceptance" / "agents" / "probe"

# What a person's shell might export -- the environment serve.sh must beat.
HOSTILE = {
    "LANGSMITH_TRACING": "true",
    "LANGCHAIN_TRACING_V2": "true",
    "LANGSMITH_API_KEY": "lsv2_pt_not_a_real_key",
}
WINDOWS = sys.platform == "win32"


@dataclass
class LocalServer:
    url: str
    probe_log: Path
    output: Path

    def records(self) -> list[dict]:
        """What the probe recorded, in every process the server started."""
        if not self.probe_log.is_file():
            return []
        lines = self.probe_log.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


@contextmanager
def local_server(workdir: Path, *, start_timeout: float = 180) -> Iterator[LocalServer]:
    bash = shutil.which("bash")
    if bash is None:
        raise RuntimeError("bash not found: scripts/serve.sh needs it")
    port = free_port()
    server = LocalServer(
        url=f"http://127.0.0.1:{port}",
        probe_log=workdir / "probe.jsonl",
        output=workdir / "server.log",
    )
    env = {
        **os.environ,
        **HOSTILE,
        "PROBE_LOG": str(server.probe_log),
        "PYTHONPATH": os.pathsep.join(filter(None, [str(PROBE), os.environ.get("PYTHONPATH")])),
    }
    with server.output.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [bash, "scripts/serve.sh", "--port", str(port), "--no-reload"],
            cwd=REPO,
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
            _stop(process)
    deadline = time.monotonic() + 15
    while port_in_use(port):
        if time.monotonic() > deadline:
            raise RuntimeError(f"the server still holds port {port} after it was stopped")
        time.sleep(0.5)


def _await_ok(server: LocalServer, process: subprocess.Popen, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"scripts/serve.sh exited {process.returncode}:\n"
                + server.output.read_text(encoding="utf-8", errors="replace")[-3000:]
            )
        try:
            with urllib.request.urlopen(server.url + "/ok", timeout=2) as answer:
                if answer.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(
        f"the server did not answer /ok within {timeout}s:\n"
        + server.output.read_text(encoding="utf-8", errors="replace")[-3000:]
    )


def _stop(process: subprocess.Popen) -> None:
    """Stop the whole tree: bash, uv, and the server's Python."""
    if WINDOWS:
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=30)
