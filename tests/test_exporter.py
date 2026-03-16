"""Tests for codilay.exporter — AI context export."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from codilay.exporter import AIExporter


def _make_exporter(
    sections=None,
    contents=None,
    closed=None,
    open_wires=None,
    project="TestProject",
):
    sections = sections or {
        "overview": {"title": "Overview", "file": "", "tags": ["overview"]},
        "auth": {"title": "Auth Module", "file": "src/auth.py", "tags": ["auth"]},
    }
    contents = contents or {
        "overview": "This project handles user authentication and authorization.",
        "auth": "The auth module validates JWT tokens.\n\n`verify_token()` is the entry point.",
    }
    closed = closed or [
        {"from": "src/main.py", "to": "src/auth.py", "type": "import"},
        {"from": "src/auth.py", "to": "src/db.py", "type": "call"},
    ]
    open_wires = open_wires or []
    return AIExporter(sections, contents, closed, open_wires, project)


# ── Markdown export ──────────────────────────────────────────────────────────


def test_export_markdown_basic():
    exp = _make_exporter()
    result = exp.export(fmt="markdown")
    assert "TestProject" in result
    assert "Auth Module" in result
    assert "verify_token()" in result


def test_export_markdown_includes_dependencies():
    exp = _make_exporter()
    result = exp.export(fmt="markdown", include_graph=True)
    assert "Dependencies" in result
    assert "src/main.py" in result
    assert "src/auth.py" in result


def test_export_markdown_excludes_graph():
    exp = _make_exporter()
    result = exp.export(fmt="markdown", include_graph=False)
    assert "Dependencies" not in result


def test_export_markdown_token_truncation():
    exp = _make_exporter()
    # Very small budget should truncate
    result = exp.export(fmt="markdown", max_tokens=10)
    assert "Truncated" in result or len(result) < 200


# ── XML export ───────────────────────────────────────────────────────────────


def test_export_xml_basic():
    exp = _make_exporter()
    result = exp.export(fmt="xml")
    assert "<codebase" in result
    assert 'project="TestProject"' in result
    assert "</codebase>" in result


def test_export_xml_sections():
    exp = _make_exporter()
    result = exp.export(fmt="xml")
    assert '<section id="auth"' in result
    assert "Auth Module" in result


def test_export_xml_dependencies():
    exp = _make_exporter()
    result = exp.export(fmt="xml", include_graph=True)
    assert "<dependencies>" in result
    assert '<dep from="src/main.py"' in result


def test_export_xml_no_graph():
    exp = _make_exporter()
    result = exp.export(fmt="xml", include_graph=False)
    assert "<dependencies>" not in result


def test_export_xml_escaping():
    exp = _make_exporter(project='Test <"Project"> & Co')
    result = exp.export(fmt="xml")
    assert "&lt;" in result
    assert "&amp;" in result


# ── JSON export ──────────────────────────────────────────────────────────────


def test_export_json_valid():
    exp = _make_exporter()
    result = exp.export(fmt="json")
    data = json.loads(result)
    assert data["project"] == "TestProject"
    assert isinstance(data["sections"], list)
    assert len(data["sections"]) == 2


def test_export_json_has_dependencies():
    exp = _make_exporter()
    result = exp.export(fmt="json", include_graph=True)
    data = json.loads(result)
    assert "dependencies" in data
    assert len(data["dependencies"]) == 2


def test_export_json_no_graph():
    exp = _make_exporter()
    result = exp.export(fmt="json", include_graph=False)
    data = json.loads(result)
    assert "dependencies" not in data


def test_export_json_section_metadata():
    exp = _make_exporter()
    result = exp.export(fmt="json")
    data = json.loads(result)
    auth_section = [s for s in data["sections"] if s["id"] == "auth"][0]
    assert auth_section["file"] == "src/auth.py"
    assert auth_section["tags"] == ["auth"]


# ── Content compression ──────────────────────────────────────────────────────


def test_compress_removes_hr():
    exp = _make_exporter()
    compressed = exp._compress_content("Before\n---\nAfter")
    assert "---" not in compressed


def test_compress_collapses_blank_lines():
    exp = _make_exporter()
    compressed = exp._compress_content("Line 1\n\n\n\n\nLine 2")
    assert "\n\n\n" not in compressed
    assert "Line 1" in compressed
    assert "Line 2" in compressed


def test_compress_strips_table_alignment():
    exp = _make_exporter()
    table = "| Name | Type |\n|---|---|\n| foo | int |"
    compressed = exp._compress_content(table)
    assert "|---|" not in compressed
    assert "foo" in compressed


def test_compress_empty_content():
    exp = _make_exporter()
    assert exp._compress_content("") == ""
    assert exp._compress_content("   ") == ""


# ── Unresolved references ────────────────────────────────────────────────────


def test_export_excludes_unresolved_by_default():
    exp = _make_exporter(
        sections={
            "overview": {"title": "Overview", "file": ""},
            "unresolved-references": {"title": "Unresolved", "file": ""},
        },
        contents={
            "overview": "Content here.",
            "unresolved-references": "Some unresolved stuff.",
        },
    )
    result = exp.export(fmt="markdown", include_unresolved=False)
    assert "Unresolved" not in result


def test_export_includes_unresolved_when_requested():
    exp = _make_exporter(
        sections={
            "overview": {"title": "Overview", "file": ""},
            "unresolved-references": {"title": "Unresolved", "file": ""},
        },
        contents={
            "overview": "Content here.",
            "unresolved-references": "Some unresolved stuff.",
        },
    )
    result = exp.export(fmt="markdown", include_unresolved=True)
    assert "Unresolved" in result


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_export_empty_sections():
    exp = _make_exporter(sections={}, contents={}, closed=[])
    result = exp.export(fmt="markdown")
    assert "TestProject" in result


def test_export_caps_dependencies_at_50():
    wires = [{"from": f"src/f{i}.py", "to": f"src/g{i}.py", "type": "import"} for i in range(80)]
    exp = _make_exporter(closed=wires)
    result = exp.export(fmt="markdown", include_graph=True)
    assert "+30 more" in result


def test_export_default_project_name():
    exp = AIExporter({}, {}, [], [], project_name="")
    result = exp.export(fmt="markdown")
    assert "Project" in result


# ── export_for_ai settings fallback ──────────────────────────────────────────


def _write_minimal_state(output_dir: str):
    """Write a minimal .codilay_state.json so export_for_ai can load it."""
    import json as _json

    state = {
        "processed": [],
        "section_index": {"overview": {"title": "Overview", "file": "", "tags": [], "deps": [], "wires_closed": []}},
        "section_contents": {"overview": "Test overview content."},
        "open_wires": [],
        "closed_wires": [],
        "parked": {},
        "park_reasons": {},
        "last_run": "2025-01-01T00:00:00+00:00",
        "mode": "full",
    }
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, ".codilay_state.json"), "w") as f:
        _json.dump(state, f)


def test_export_for_ai_uses_settings_format():
    """When fmt=None, export_for_ai should use settings.export_default_format."""
    import json as _json
    import pathlib

    from codilay.exporter import export_for_ai

    with tempfile.TemporaryDirectory() as tmp:
        _write_minimal_state(tmp)

        # Write a settings file that specifies xml format, no token limit
        settings_dir = os.path.join(tmp, ".codilay_settings")
        settings_file = os.path.join(settings_dir, "settings.json")
        os.makedirs(settings_dir)
        with open(settings_file, "w") as f:
            _json.dump({"export_default_format": "xml", "export_max_tokens": 0}, f)

        with patch("codilay.settings.SETTINGS_FILE", pathlib.Path(settings_file)):
            result = export_for_ai(tmp, fmt=None)

    assert "<codebase" in result  # XML format was used


def test_export_for_ai_explicit_fmt_overrides_settings():
    """An explicit fmt argument must override the settings preference."""
    import json as _json
    import pathlib

    from codilay.exporter import export_for_ai

    with tempfile.TemporaryDirectory() as tmp:
        _write_minimal_state(tmp)

        settings_dir = os.path.join(tmp, ".codilay_settings")
        settings_file = os.path.join(settings_dir, "settings.json")
        os.makedirs(settings_dir)
        with open(settings_file, "w") as f:
            _json.dump({"export_default_format": "xml", "export_max_tokens": 0}, f)

        with patch("codilay.settings.SETTINGS_FILE", pathlib.Path(settings_file)):
            result = export_for_ai(tmp, fmt="json")

    # Should be JSON, not XML
    data = json.loads(result)
    assert "sections" in data


def test_export_for_ai_uses_settings_max_tokens():
    """When max_tokens=None, the settings token limit is applied."""
    import json as _json
    import pathlib

    from codilay.exporter import export_for_ai

    with tempfile.TemporaryDirectory() as tmp:
        _write_minimal_state(tmp)

        settings_dir = os.path.join(tmp, ".codilay_settings")
        settings_file = os.path.join(settings_dir, "settings.json")
        os.makedirs(settings_dir)
        # Very tight budget → truncated
        with open(settings_file, "w") as f:
            _json.dump({"export_default_format": "markdown", "export_max_tokens": 10}, f)

        with patch("codilay.settings.SETTINGS_FILE", pathlib.Path(settings_file)):
            result = export_for_ai(tmp, fmt="markdown", max_tokens=None)

    # With only 10 tokens the result must be truncated
    assert "Truncated" in result or len(result) < 200


def test_export_for_ai_zero_max_tokens_means_no_limit():
    """export_max_tokens=0 in settings means unlimited (no truncation)."""
    import json as _json
    import pathlib

    from codilay.exporter import export_for_ai

    with tempfile.TemporaryDirectory() as tmp:
        _write_minimal_state(tmp)

        settings_dir = os.path.join(tmp, ".codilay_settings")
        settings_file = os.path.join(settings_dir, "settings.json")
        os.makedirs(settings_dir)
        with open(settings_file, "w") as f:
            _json.dump({"export_default_format": "markdown", "export_max_tokens": 0}, f)

        with patch("codilay.settings.SETTINGS_FILE", pathlib.Path(settings_file)):
            result = export_for_ai(tmp, fmt="markdown")

    assert "Truncated" not in result


def test_export_for_ai_missing_state_raises():
    """export_for_ai raises FileNotFoundError when no state file exists."""
    from codilay.exporter import export_for_ai

    with tempfile.TemporaryDirectory() as tmp:
        empty_dir = os.path.join(tmp, "no_state_here")
        os.makedirs(empty_dir)
        try:
            export_for_ai(empty_dir)
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass
