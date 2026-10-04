"""The architecture rules as functions, so each can be run on this package -- and
on a fixture package built to break it.

A check you have not watched fail is a check you do not have. import-linter
exits 0 when it cannot find the root package, and an allowlist over an empty
import set passes while checking nothing; both have happened. So every rule
here is proved twice: it holds for `starter`, and it fails for a fixture.
"""

from __future__ import annotations

import ast
import io
import sys
import tomllib
from collections.abc import Iterable
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PYPROJECT = REPO / "pyproject.toml"

# What each layer may import beyond the standard library and its own package.
# Allowlists, not denylists: a denylist names the packages that existed when it
# was written, and the next dependency walks straight past it.
ALLOWED_EXTERNALS = {
    "domain": frozenset(),
    "application": frozenset({"langchain_core", "pydantic"}),
}

# Runtimes confined to the agents adapter. Checked at package granularity --
# grimp records `langgraph`, never `langgraph.errors` -- so there are no
# submodule exceptions to make, and none to get wrong.
CONFINED_RUNTIMES = frozenset({"langgraph", "deepagents"})
AGENTS_SUBPACKAGE = "infrastructure.agents"

ENV_READERS = frozenset({"environ", "getenv", "putenv", "unsetenv"})


def importlinter_config() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["importlinter"]


def root_package() -> str:
    """Declared once, in [tool.importlinter]; everything else reads it from there."""
    return importlinter_config()["root_package"]


def lint(config_file: Path | None = None) -> tuple[bool, str]:
    """Run import-linter's contracts, returning (all kept, the report)."""
    from importlinter import configuration
    from importlinter.application.use_cases import lint_imports

    configuration.configure()
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        passed = lint_imports(
            config_filename=str(config_file) if config_file else None,
            cache_dir=None,
            no_logo=True,
        )
    return passed, buffer.getvalue()


def layers_config_for(package: str) -> str:
    """This project's layers contract, rewritten for another root package (INI)."""
    contract = next(c for c in importlinter_config()["contracts"] if c["type"] == "layers")
    root = root_package()
    layers = "\n".join(
        "    " + layer.replace(f"{root}.", f"{package}.") for layer in contract["layers"]
    )
    return (
        f"[importlinter]\nroot_package = {package}\n\n"
        f"[importlinter:contract:layers]\nname = {contract['name']}\ntype = layers\n"
        f"layers =\n{layers}\n"
    )


def imports_outside(package: str, layer: str, allowed: frozenset[str]) -> list[tuple[str, str]]:
    """Every (module, external package) where `layer` imports beyond what is allowed."""
    import grimp

    graph = grimp.build_graph(package, include_external_packages=True, cache_dir=None)
    prefix = f"{package}.{layer}"
    modules = {m for m in graph.modules if m == prefix or m.startswith(prefix + ".")}
    if not modules:
        raise AssertionError(f"no modules under {prefix}: the check would pass vacuously")
    return sorted(
        (module, imported)
        for module in modules
        for imported in graph.find_modules_directly_imported_by(module)
        if not imported.startswith(package)
        and imported not in sys.stdlib_module_names
        and imported not in allowed
    )


def runtimes_outside_agents(package: str) -> list[tuple[str, str]]:
    """Every (module, runtime) where a confined runtime is imported outside the agents adapter."""
    import grimp

    graph = grimp.build_graph(package, include_external_packages=True, cache_dir=None)
    agents = f"{package}.{AGENTS_SUBPACKAGE}"
    return sorted(
        (module, imported)
        for module in graph.modules
        if module.startswith(package) and not (module == agents or module.startswith(agents + "."))
        for imported in graph.find_modules_directly_imported_by(module)
        if imported in CONFINED_RUNTIMES
    )


def python_files(source: Path, layer: str | None = None) -> Iterable[tuple[str, Path]]:
    """(layer, path) for every module under a package directory."""
    for path in sorted(source.rglob("*.py")):
        parts = path.relative_to(source).parts
        found = parts[0] if len(parts) > 1 else ""
        if layer is None or found == layer:
            yield found, path


def environment_reads_outside_config(source: Path) -> list[str]:
    """`os.environ`, `os.getenv`, `from os import environ`, or dotenv -- outside config/."""
    found = []
    for layer, path in python_files(source):
        if layer == "config":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr in ENV_READERS
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
            ):
                found.append(f"{path.name}:{node.lineno} os.{node.attr}")
            elif isinstance(node, ast.ImportFrom) and node.module == "os":
                found += [
                    f"{path.name}:{node.lineno} from os import {a.name}"
                    for a in node.names
                    if a.name in ENV_READERS
                ]
            elif isinstance(node, ast.ImportFrom | ast.Import):
                names = (
                    [node.module]
                    if isinstance(node, ast.ImportFrom)
                    else [a.name for a in node.names]
                )
                found += [
                    f"{path.name}:{node.lineno} import {n}"
                    for n in names
                    if n and n.split(".")[0] == "dotenv"
                ]
    return found


def exits_outside_cli(source: Path) -> list[str]:
    """`sys.exit`, `exit()`, `quit()` or `raise SystemExit` -- outside cli/."""
    found = []
    for layer, path in python_files(source):
        if layer == "cli":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "exit"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "sys"
                ):
                    found.append(f"{path.name}:{node.lineno} sys.exit")
                elif isinstance(func, ast.Name) and func.id in ("exit", "quit"):
                    found.append(f"{path.name}:{node.lineno} {func.id}()")
            elif isinstance(node, ast.Raise) and node.exc is not None:
                exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
                if isinstance(exc, ast.Name) and exc.id == "SystemExit":
                    found.append(f"{path.name}:{node.lineno} raise SystemExit")
    return found


def build_package(base: Path, name: str, files: dict[str, str]) -> Path:
    """Write a throwaway package: {"domain/routing.py": "import langgraph"} and the __init__s."""
    root = base / name
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    for directory in [root, *(p for p in root.rglob("*") if p.is_dir())]:
        (directory / "__init__.py").touch()
    return root
