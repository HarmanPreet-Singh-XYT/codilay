"""Tests for codilay.prompts — system_prompt style modifiers."""

from unittest.mock import MagicMock

from codilay.prompts import system_prompt


def _make_config(notes="", instructions=""):
    cfg = MagicMock()
    cfg.notes = notes
    cfg.instructions = instructions
    return cfg


# ── Base content always present ───────────────────────────────────────────────


def test_system_prompt_contains_base_content():
    cfg = _make_config()
    result = system_prompt(cfg)
    assert "CodiLay" in result
    assert "wire" in result.lower()
    assert "JSON" in result


# ── response_style modifier ───────────────────────────────────────────────────


def test_response_style_technical_no_extra_note():
    """Default 'technical' style adds no extra note."""
    cfg = _make_config()
    result = system_prompt(cfg, response_style="technical")
    assert "Response style:" not in result


def test_response_style_concise_adds_note():
    cfg = _make_config()
    result = system_prompt(cfg, response_style="concise")
    assert "Response style:" in result
    assert "concise" in result.lower()


def test_response_style_narrative_adds_note():
    cfg = _make_config()
    result = system_prompt(cfg, response_style="narrative")
    assert "Response style:" in result
    assert "narrative" in result.lower()


def test_response_style_technical_absent_when_concise():
    """When concise is requested, 'technical' note should NOT appear."""
    cfg = _make_config()
    result_concise = system_prompt(cfg, response_style="concise")
    result_tech = system_prompt(cfg, response_style="technical")
    # concise result must differ from technical
    assert result_concise != result_tech


# ── detail_level modifier ─────────────────────────────────────────────────────


def test_detail_level_standard_no_extra_note():
    cfg = _make_config()
    result = system_prompt(cfg, detail_level="standard")
    assert "Detail level:" not in result


def test_detail_level_brief_adds_note():
    cfg = _make_config()
    result = system_prompt(cfg, detail_level="brief")
    assert "Detail level:" in result
    assert "brief" in result.lower()


def test_detail_level_deep_adds_note():
    cfg = _make_config()
    result = system_prompt(cfg, detail_level="deep")
    assert "Detail level:" in result
    assert "deep" in result.lower()


# ── include_examples modifier ─────────────────────────────────────────────────


def test_include_examples_true_adds_snippet_note():
    cfg = _make_config()
    result = system_prompt(cfg, include_examples=True)
    assert "examples" in result.lower() or "snippet" in result.lower()


def test_include_examples_false_adds_do_not_note():
    cfg = _make_config()
    result = system_prompt(cfg, include_examples=False)
    assert "Do NOT include code examples" in result


def test_include_examples_notes_differ():
    cfg = _make_config()
    result_with = system_prompt(cfg, include_examples=True)
    result_without = system_prompt(cfg, include_examples=False)
    assert result_with != result_without


# ── All modifiers combined ────────────────────────────────────────────────────


def test_all_modifiers_combined():
    cfg = _make_config()
    result = system_prompt(
        cfg,
        response_style="narrative",
        detail_level="deep",
        include_examples=False,
    )
    assert "narrative" in result.lower()
    assert "deep" in result.lower()
    assert "Do NOT include code examples" in result


# ── Notes and instructions sections ──────────────────────────────────────────


def test_notes_section_included():
    cfg = _make_config(notes="This is a payment processing service.")
    result = system_prompt(cfg)
    assert "Project context:" in result
    assert "payment processing" in result


def test_instructions_section_included():
    cfg = _make_config(instructions="Always use British English.")
    result = system_prompt(cfg)
    assert "Special instructions:" in result
    assert "British English" in result


def test_empty_notes_not_included():
    cfg = _make_config(notes="")
    result = system_prompt(cfg)
    assert "Project context:" not in result


def test_empty_instructions_not_included():
    cfg = _make_config(instructions="")
    result = system_prompt(cfg)
    assert "Special instructions:" not in result
