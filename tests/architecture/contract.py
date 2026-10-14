"""The architecture rules as functions, so each can be run on this package -- and
on a fixture package built to break it.

A check you have not watched fail is a check you do not have. import-linter
exits 0 when it cannot find the root package, and an allowlist over an empty
import set passes while checking nothing; both have happened. So every rule
here is proved twice: it holds for `starter`, and it fails for a fixture.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import io
import json
import os
import re
import shlex
import subprocess
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
    # Reads .env into a dict -- nothing more: no client, no SDK.
    "config": frozenset({"dotenv"}),
}

# Runtimes confined to the agents adapter. Checked at package granularity --
# grimp records `langgraph`, never `langgraph.errors` -- so there are no
# submodule exceptions to make, and none to get wrong.
CONFINED_RUNTIMES = frozenset({"langgraph", "deepagents"})
AGENTS_SUBPACKAGE = "infrastructure.agents"

ENV_READERS = frozenset({"environ", "getenv", "putenv", "unsetenv"})

# The agents adapter composes graphs and builds no client of its own: beyond the
# runtimes and their abstractions, an import there is a dependency that did not
# arrive through composition -- and a node no fake model can replace.
AGENTS_ALLOWED_EXTERNALS = frozenset(
    {"langgraph", "deepagents", "langchain", "langchain_core", "pydantic", "typing_extensions"}
)
# A model client built from a string, where no fake can be passed in instead.
INLINE_MODEL_BUILDERS = frozenset({"init_chat_model"})
AGENT_FACTORIES = frozenset({"create_agent", "create_deep_agent", "create_react_agent"})

# langgraph.json names graphs only through the registry, under stable ids.
REGISTRY = "infrastructure/agents/registry.py"
GRAPH_ID = re.compile(r"^[a-z][a-z0-9_-]*$")


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


STORES_PREFIX = "infrastructure/stores/"


SQLITE_MODULES = frozenset({"sqlite3", "sqlite3.dbapi2", "_sqlite3"})


def _of_module(attribute: ast.Attribute, modules: set[str]) -> bool:
    """Whether `attribute` is reached from one of `modules`, through `dbapi2` or not."""
    owner = attribute.value
    if isinstance(owner, ast.Attribute) and owner.attr == "dbapi2":
        owner = owner.value
    return isinstance(owner, ast.Name) and owner.id in modules


def databases_opened_outside_stores(source: Path) -> list[str]:
    """A database opened outside infrastructure/stores/, the only place one is
    (ADR 0006): any reference to `connect` of `sqlite3`, its `dbapi2` or the C
    module `_sqlite3` or their `Connection` -- called, subclassed or bound to
    another name, however the module or the name is bound -- or a star import
    from them. Importing `sqlite3` for its error classes, or naming
    `Connection` in a type annotation or as `isinstance`'s or `issubclass`'s
    class, opens nothing. Out of reach: a module imported by `importlib` from
    a string."""
    found = []
    for path in sorted(source.rglob("*.py")):
        rel = path.relative_to(source).as_posix()
        if rel.startswith(STORES_PREFIX):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        # Names bound to one of the modules, and to an opener imported by name.
        modules: set[str] = set()
        connects: set[str] = set()
        classes: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in SQLITE_MODULES:
                        # `import sqlite3.dbapi2` binds `sqlite3`; with `as`, the module itself.
                        modules.add(a.asname or a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module in SQLITE_MODULES:
                for a in node.names:
                    if a.name == "*":
                        found.append(f"{rel}:{node.lineno} from {node.module} import *")
                    elif a.name == "connect":
                        connects.add(a.asname or a.name)
                    elif a.name == "Connection":
                        classes.add(a.asname or a.name)
                    elif a.name == "dbapi2":
                        modules.add(a.asname or a.name)

        typing_only = _typing_only_nodes(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and _of_module(node, modules):
                if node.attr == "connect" or (
                    node.attr == "Connection" and id(node) not in typing_only
                ):
                    found.append(f"{rel}:{node.lineno} sqlite3.{node.attr}")
            elif isinstance(node, ast.Name) and (
                node.id in connects or (node.id in classes and id(node) not in typing_only)
            ):
                found.append(f"{rel}:{node.lineno} {node.id}")
    return found


def _typing_only_nodes(tree: ast.AST) -> set[int]:
    """The nodes that name a class without using it: inside a type annotation,
    or the class argument of `isinstance` and `issubclass` -- but never a class
    called there, since Python evaluates annotations and that call opens a
    database. A type alias outside an annotation (`Callable[[],
    sqlite3.Connection]`) is not spared: a false positive, stated."""
    roots: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.arg | ast.AnnAssign) and node.annotation is not None:
            roots.append(node.annotation)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.returns:
            roots.append(node.returns)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("isinstance", "issubclass")
            and len(node.args) == 2
        ):
            roots.append(node.args[1])
    inside = [inner for root in roots for inner in ast.walk(root)]
    called = {id(node.func) for node in inside if isinstance(node, ast.Call)}
    return {id(node) for node in inside} - called


def agents_dir(source: Path) -> Path:
    return source / "infrastructure" / "agents"


def models_built_inline(source: Path) -> list[str]:
    """`init_chat_model(...)`, or a string model given to `create_agent` and its kin,
    anywhere in the agents adapter. The model arrives as an object, built outside."""
    found = []
    for path in sorted(agents_dir(source).rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in INLINE_MODEL_BUILDERS:
                found.append(f"{path.name}:{node.lineno} {name}()")
            elif name in AGENT_FACTORIES:
                model = node.args[0] if node.args else None
                model = next((k.value for k in node.keywords if k.arg == "model"), model)
                if isinstance(model, ast.Constant) and isinstance(model.value, str):
                    found.append(f"{path.name}:{node.lineno} {name}(model={model.value!r})")
    return found


def top_level_names(path: Path) -> set[str]:
    """Every name a module binds at its top level: what it exports."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import | ast.ImportFrom):
            names |= {(a.asname or a.name).split(".")[0] for a in node.names}
    return names


def registration_problems(config: Path, source: Path, package: str) -> list[str]:
    """What is wrong with a langgraph.json, judged against the registry module.

    Every graph names a top-level name of infrastructure/agents/registry.py -- as
    a path or as a dotted module -- under a stable id. The file has no "env": the
    server loads it over the environment scripts/serve.sh starts it from.
    """
    data = json.loads(config.read_text(encoding="utf-8"))
    problems = []
    if "env" in data:
        problems.append('"env": the server loads it over the local-only environment')
    registry = source / REGISTRY
    exported = top_level_names(registry) if registry.is_file() else set()
    module = f"{package}.{REGISTRY[:-3].replace('/', '.')}"
    for graph_id, spec in (data.get("graphs") or {}).items():
        if not GRAPH_ID.fullmatch(graph_id):
            problems.append(f"graph id {graph_id!r}: not lowercase letters, digits, - and _")
        target = str(spec.get("path") if isinstance(spec, dict) else spec)
        location, _, name = target.rpartition(":")
        if location.endswith(".py"):
            in_registry = (config.parent / location).resolve() == registry.resolve()
        else:
            in_registry = location == module
        if not in_registry:
            problems.append(f"graph {graph_id!r}: {target} is not in {REGISTRY}")
        elif name not in exported:
            problems.append(f"graph {graph_id!r}: {REGISTRY} binds no {name!r}")
    return problems


def uncompiled_registrations(config: Path) -> list[str]:
    """Each graph langgraph.json names that, loaded the way the server loads it, is
    not a compiled graph -- a factory, an uncompiled `StateGraph`, anything else.

    The server would accept a factory, or compile a `StateGraph` itself. The rule
    here is narrower (graphs.md, "Registration"): the registry exports what the
    factory compiled, so the graph served is the graph the tests ran.
    """
    from langgraph.pregel import Pregel  # here, not at the top: only once a graph exists

    problems = []
    for graph_id, spec in (
        json.loads(config.read_text(encoding="utf-8")).get("graphs") or {}
    ).items():
        target = str(spec.get("path") if isinstance(spec, dict) else spec)
        location, _, name = target.rpartition(":")
        if location.endswith(".py"):
            module_spec = importlib.util.spec_from_file_location(
                f"_registered_{graph_id}", config.parent / location
            )
            module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
        else:
            module = importlib.import_module(location)
        value = getattr(module, name, None)
        if not isinstance(value, Pregel):
            problems.append(
                f"graph {graph_id!r}: {target} is a {type(value).__name__}, not a compiled graph"
            )
    return problems


def langgraph_validate(config: Path) -> subprocess.CompletedProcess[str]:
    """`langgraph validate` on a config: its schema -- JSON, a non-empty `graphs`,
    `python_version`, `dependencies`. It never loads a graph: a path to a file that
    does not exist passes it, which is why `uncompiled_registrations` exists.

    LANGGRAPH_CLI_NO_ANALYTICS must be exactly "1": anything else, "true"
    included, and the command POSTs analytics to Supabase -- measured with
    langgraph-cli 0.4.33 (register-first-graph, frame.md). PYTHONUTF8=1 because on
    Windows the CLI's emoji output crashes under cp1252.
    """
    env = {**os.environ, "LANGGRAPH_CLI_NO_ANALYTICS": "1", "PYTHONUTF8": "1"}
    return subprocess.run(
        [sys.executable, "-m", "langgraph_cli", "validate", "-c", str(config)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=config.parent,
        timeout=120,
    )


FACTORY = "infrastructure/agents/factory.py"
AGENTS_PREFIX = "infrastructure/agents/"
GRAPH_RUNTIMES = ("langgraph", "deepagents", "langchain.agents")
# `.compile()` on these is not a graph -- a regex, most often.
NOT_GRAPH_COMPILERS = frozenset({"re", "regex"})


def _import_names(node: ast.AST) -> list[str]:
    """What one import statement brings in, as dotted names. `from a import b`
    gives both `a` and `a.b`: `b` may itself be a module (`from langchain import
    agents`). Relative imports name this package, never a runtime: none."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module and not node.level:
        return [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
    return []


def _within(name: str, package: str) -> bool:
    return name == package or name.startswith(package + ".")


def graphs_compiled_outside_factory(source: Path) -> list[str]:
    """`create_agent` and its kin -- under any name they were imported as -- or a
    `.compile()` that may be a graph's, anywhere in the package but the factory.
    A `.compile()` counts anywhere under infrastructure/agents/, where a builder
    can arrive by import, and in any module importing a graph runtime; never on
    a regex. A graph compiled elsewhere is a graph the tests never ran -- the
    registry could export one without its budget and every test would stay green
    (register-first-graph, verify.md)."""
    found = []
    for path in sorted(source.rglob("*.py")):
        rel = path.relative_to(source).as_posix()
        if rel == FACTORY:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        factories = set(AGENT_FACTORIES) | {
            alias.asname or alias.name
            for node in imports
            if node.module and any(_within(node.module, r) for r in GRAPH_RUNTIMES)
            for alias in node.names
            if alias.name in AGENT_FACTORIES
        }
        uses_runtime = any(
            _within(name, runtime)
            for node in ast.walk(tree)
            for name in _import_names(node)
            for runtime in GRAPH_RUNTIMES
        )
        may_compile = rel.startswith(AGENTS_PREFIX) or uses_runtime
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute):
                name = func.attr
                receiver = func.value.id if isinstance(func.value, ast.Name) else None
            else:
                name, receiver = getattr(func, "id", None), None
            compiles = name == "compile" and may_compile and receiver not in NOT_GRAPH_COMPILERS
            if name in factories or compiles:
                found.append(f"{rel}:{node.lineno} {name}()")
    return found


def agent_runtime_imports_outside_agents(source: Path) -> list[str]:
    """`langchain.agents` imported outside infrastructure/agents/, in any spelling.
    `create_agent` compiles a graph (ADR 0003), and grimp records only the
    top-level `langchain`, which models.py may need for a provider -- so the
    submodule is checked here, once per import statement."""
    found = []
    for path in sorted(source.rglob("*.py")):
        rel = path.relative_to(source).as_posix()
        if rel.startswith(AGENTS_PREFIX):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            hit = next((n for n in _import_names(node) if _within(n, "langchain.agents")), None)
            if hit:
                found.append(f"{rel} imports {hit}")
    return found


MODELS_MODULE = "infrastructure/models.py"
# A model's class, by its name: a chat model (ChatOpenAI, AzureChatOpenAI,
# GenericFakeChatModel), a completion model (OllamaLLM, OpenAI) or embeddings --
# not langchain_core's chat data (ChatPromptTemplate, ChatMessage, ChatResult,
# ChatSession, ChatModelStream and kin), nor an error class. A partner package's
# other classes (`langchain_chroma.Chroma`) build no model.
MODEL_CLASS = re.compile(
    r"^(?!\w*Error$)"
    r"(\w*Chat(?!Prompt|Message|Generation|Result|Session|Loader|ModelStream)[A-Z]\w*"
    r"|\w*LLM|\w*Embeddings|(Azure)?OpenAI)$"
)
# A provider's own SDK: every client it makes is a model client, whatever its
# name (`ollama.Client`) -- imported from the SDK, or called through it; its
# error classes (`openai.APITimeoutError`) are not.
PROVIDER_SDKS = frozenset({"openai", "anthropic", "ollama", "mistralai", "cohere"})


def models_built_outside_models(source: Path) -> list[str]:
    """A model constructed anywhere in the package but infrastructure/models.py
    -- `init_chat_model(...)`, a model's class called, or a provider SDK's client.
    A second place that builds a model is a second configuration path, and the
    two will disagree (.claude/rules/python/infrastructure.md)."""
    found = []
    for path in sorted(source.rglob("*.py")):
        rel = path.relative_to(source).as_posix()
        if rel == MODELS_MODULE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        # The local names of a builder or a model's class, whatever they are bound
        # as, and of a provider SDK's module.
        builders: set[str] = set()
        sdk_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                from_sdk = node.module.split(".")[0] in PROVIDER_SDKS
                for alias in node.names:
                    if (
                        (from_sdk and not alias.name.endswith("Error"))
                        or alias.name in INLINE_MODEL_BUILDERS
                        or MODEL_CLASS.match(alias.name)
                    ):
                        builders.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in PROVIDER_SDKS:
                        sdk_modules.add(alias.asname or root)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute):
                name = func.attr
                through_sdk = (
                    isinstance(func.value, ast.Name)
                    and func.value.id in sdk_modules
                    and name[:1].isupper()
                    and not name.endswith("Error")
                )
            else:
                name, through_sdk = getattr(func, "id", None), False
            if name and (
                name in INLINE_MODEL_BUILDERS
                or name in builders
                or MODEL_CLASS.match(name)
                or through_sdk
            ):
                found.append(f"{rel}:{node.lineno} {name}()")
    return found


def shell_exports(script: str) -> dict[str, str]:
    """The variables a shell script's `export NAME=value ...` lines set."""
    exported = {}
    for line in script.splitlines():
        if line.startswith("export "):
            for word in shlex.split(line[len("export ") :]):
                name, _, value = word.partition("=")
                exported[name] = value
    return exported


def local_only_drift(suite: dict[str, str], settings_env: dict[str, str]) -> list[str]:
    """Where the suite's local-only environment and the agent's settings disagree,
    on every LangSmith, LangChain and LangGraph variable either one sets."""
    prefixes = ("LANGSMITH_", "LANGCHAIN_", "LANGGRAPH_")
    expected = {k: v for k, v in settings_env.items() if k.startswith(prefixes)}
    problems = [
        f"{k}: the suite sets {suite.get(k)!r}, the settings {v!r}"
        for k, v in sorted(expected.items())
        if suite.get(k) != v
    ]
    problems += [
        f"{k}: set by the suite, not by the settings" for k in sorted(set(suite) - set(expected))
    ]
    return problems


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
