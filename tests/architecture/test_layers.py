"""The layer contract in pyproject.toml, run as a test -- and proved able to fail.

import-linter's console script exits 0 when it cannot find the root package, so
a test that checked only an exit code would pass while checking nothing. This
drives the Python API, asserts a contract was actually evaluated, and then
proves the contract breaks on a fixture package that crosses each boundary.
"""

from __future__ import annotations

import uuid

import pytest

from .contract import build_package, layers_config_for, lint


def test_the_linter_actually_evaluates_the_contract():
    """Guard against a vacuous pass: a contract ran, against a package it found."""
    _passed, report = lint()
    assert "Could not find package" not in report, report
    assert "Contracts: " in report, f"no contract summary was produced:\n{report}"
    assert "0 kept, 0 broken" not in report, f"no contract ran:\n{report}"


def test_the_package_keeps_its_layers():
    passed, report = lint()
    assert passed, f"a layer boundary was crossed:\n{report}"


def _fixture(tmp_path, monkeypatch, importer: str, imported: str) -> bool:
    name = f"layers_{uuid.uuid4().hex[:8]}"
    build_package(
        tmp_path,
        name,
        {
            f"{layer}/__init__.py": ""
            for layer in ("domain", "config", "application", "infrastructure", "cli")
        }
        | {
            f"{importer}/uses.py": f"from {name}.{imported} import thing\n",
            f"{imported}/thing.py": "x = 1\n",
        },
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    config = tmp_path / ".importlinter"
    config.write_text(layers_config_for(name), encoding="utf-8")
    passed, _report = lint(config)
    return passed


@pytest.mark.parametrize(
    ("importer", "imported"),
    [
        ("domain", "application"),
        ("domain", "cli"),
        ("application", "config"),
        ("config", "application"),
        ("application", "infrastructure"),
        ("infrastructure", "cli"),
    ],
)
def test_a_dependency_pointing_outward_breaks_the_contract(
    tmp_path, monkeypatch, importer, imported
):
    assert not _fixture(tmp_path, monkeypatch, importer, imported)


@pytest.mark.parametrize(
    ("importer", "imported"),
    [
        ("cli", "infrastructure"),
        ("infrastructure", "application"),
        ("infrastructure", "config"),
        ("application", "domain"),
        ("config", "domain"),
    ],
)
def test_counter_example_a_dependency_pointing_inward_is_kept(
    tmp_path, monkeypatch, importer, imported
):
    assert _fixture(tmp_path, monkeypatch, importer, imported)
