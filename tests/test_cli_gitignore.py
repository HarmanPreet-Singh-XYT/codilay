"""Tests for _write_gitignore_for_doc_location in codilay.cli."""

import os
import tempfile
from unittest.mock import MagicMock

from codilay.cli import _write_gitignore_for_doc_location


def _mock_console():
    return MagicMock()


# ── Scenario A: "codilay" ─────────────────────────────────────────────────────


def test_gitignore_codilay_scenario_creates_file():
    with tempfile.TemporaryDirectory() as tmp:
        _write_gitignore_for_doc_location(tmp, "codilay", _mock_console())
        gitignore = os.path.join(tmp, ".gitignore")
        assert os.path.exists(gitignore)


def test_gitignore_codilay_scenario_ignores_state():
    with tempfile.TemporaryDirectory() as tmp:
        _write_gitignore_for_doc_location(tmp, "codilay", _mock_console())
        content = open(os.path.join(tmp, ".gitignore")).read()
        assert "codilay/.codilay_state.json" in content
        assert "codilay/chat/" in content or "codilay/memory/" in content


def test_gitignore_codilay_scenario_does_not_ignore_dir_entirely():
    """In 'codilay' scenario, CODEBASE.md should stay committed — codilay/ must NOT be fully ignored."""
    with tempfile.TemporaryDirectory() as tmp:
        _write_gitignore_for_doc_location(tmp, "codilay", _mock_console())
        content = open(os.path.join(tmp, ".gitignore")).read()
        # The bare "codilay/" line (which ignores everything) must not be present
        lines = [line.strip() for line in content.splitlines()]
        assert "codilay/" not in lines


# ── Scenario B: "docs" ────────────────────────────────────────────────────────


def test_gitignore_docs_scenario_ignores_full_codilay_dir():
    with tempfile.TemporaryDirectory() as tmp:
        _write_gitignore_for_doc_location(tmp, "docs", _mock_console())
        content = open(os.path.join(tmp, ".gitignore")).read()
        lines = [line.strip() for line in content.splitlines()]
        assert "codilay/" in lines


def test_gitignore_docs_scenario_no_state_file_line():
    """In 'docs' scenario, individual state file entries are redundant — the whole dir is ignored."""
    with tempfile.TemporaryDirectory() as tmp:
        _write_gitignore_for_doc_location(tmp, "docs", _mock_console())
        content = open(os.path.join(tmp, ".gitignore")).read()
        assert "codilay/.codilay_state.json" not in content


# ── Scenario C: "local" ───────────────────────────────────────────────────────


def test_gitignore_local_scenario_ignores_codilay_dir():
    with tempfile.TemporaryDirectory() as tmp:
        _write_gitignore_for_doc_location(tmp, "local", _mock_console())
        content = open(os.path.join(tmp, ".gitignore")).read()
        lines = [line.strip() for line in content.splitlines()]
        assert "codilay/" in lines


def test_gitignore_local_scenario_ignores_docs_codebase_md():
    with tempfile.TemporaryDirectory() as tmp:
        _write_gitignore_for_doc_location(tmp, "local", _mock_console())
        content = open(os.path.join(tmp, ".gitignore")).read()
        assert "docs/CODEBASE.md" in content


# ── Marker written ────────────────────────────────────────────────────────────


def test_gitignore_contains_marker():
    for scenario in ("codilay", "docs", "local"):
        with tempfile.TemporaryDirectory() as tmp:
            _write_gitignore_for_doc_location(tmp, scenario, _mock_console())
            content = open(os.path.join(tmp, ".gitignore")).read()
            assert "# CodiLay" in content, f"Marker missing in '{scenario}' scenario"


# ── Idempotency ───────────────────────────────────────────────────────────────


def test_gitignore_idempotent_no_duplicate_blocks():
    """Calling the function twice must not duplicate the CodiLay block."""
    with tempfile.TemporaryDirectory() as tmp:
        cons = _mock_console()
        _write_gitignore_for_doc_location(tmp, "codilay", cons)
        _write_gitignore_for_doc_location(tmp, "codilay", cons)
        content = open(os.path.join(tmp, ".gitignore")).read()
        assert content.count("# CodiLay") == 1


def test_gitignore_idempotent_skips_when_marker_present():
    """Second call should be a no-op; console.print should note the skip."""
    with tempfile.TemporaryDirectory() as tmp:
        cons = _mock_console()
        _write_gitignore_for_doc_location(tmp, "docs", cons)
        _write_gitignore_for_doc_location(tmp, "docs", cons)
        # The second call should have triggered the "already contains" print
        assert cons.print.call_count >= 2
        second_call_args = str(cons.print.call_args_list[-1])
        assert "skipping" in second_call_args.lower() or "already" in second_call_args.lower()


# ── Appends to existing .gitignore ────────────────────────────────────────────


def test_gitignore_appends_to_existing_content():
    with tempfile.TemporaryDirectory() as tmp:
        gitignore = os.path.join(tmp, ".gitignore")
        with open(gitignore, "w") as f:
            f.write("*.pyc\n__pycache__/\n")
        _write_gitignore_for_doc_location(tmp, "codilay", _mock_console())
        content = open(gitignore).read()
        assert "*.pyc" in content  # Original content preserved
        assert "# CodiLay" in content  # New content appended
