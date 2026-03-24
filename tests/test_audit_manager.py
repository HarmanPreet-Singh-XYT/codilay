import json
import os
from unittest.mock import MagicMock

import pytest

from codilay.audit_manager import AuditManager


@pytest.fixture
def temp_output_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.call.return_value = {
        "answer": (
            "FINDING: Test Finding\n"
            "Severity: HIGH\n"
            "File: foo.py\n"
            "Line: 42\n"
            "Evidence: bad code\n"
            "Impact: severe\n"
            "Fix: fix it"
        )
    }
    return llm


@pytest.fixture
def mock_scanner(tmp_path):
    scanner = MagicMock()
    scanner.target_path = str(tmp_path)
    scanner.get_all_files.return_value = ["app.py", "utils.py", "routes.py"]
    scanner.read_file.return_value = "def foo():\n    pass\n"
    return scanner


def test_audit_manager_init(mock_llm, temp_output_dir):
    manager = AuditManager(mock_llm, temp_output_dir)
    assert manager.output_dir == temp_output_dir
    assert os.path.exists(manager.audits_dir)
    assert manager.index_path == os.path.join(manager.audits_dir, "audit_index.json")


def test_get_index_empty(mock_llm, temp_output_dir):
    manager = AuditManager(mock_llm, temp_output_dir)
    index = manager.get_index()
    assert index == {"runs": []}


def test_save_and_get_index(mock_llm, temp_output_dir):
    manager = AuditManager(mock_llm, temp_output_dir)
    test_index = {"runs": [{"type": "security", "mode": "passive"}]}
    manager.save_index(test_index)

    index = manager.get_index()
    assert index == test_index


def test_build_planner_prompt(mock_llm, temp_output_dir):
    manager = AuditManager(mock_llm, temp_output_dir)
    prompt = manager._build_planner_prompt(
        audit_type="security", sections={"file1.py": "def test(): pass"}, open_wires=[], closed_wires=[]
    )
    assert "audit plan" in prompt.lower() or "AUDIT PLAN" in prompt or "audit planner" in prompt.lower()
    assert "vulnerabilities" in prompt.lower() or "security" in prompt.lower()
    assert "file1.py" in prompt
    assert "CONCERN:" in prompt


def test_passive_run_audit(mock_llm, temp_output_dir):
    manager = AuditManager(mock_llm, temp_output_dir)
    result = manager.run_audit(
        audit_type="security",
        mode="passive",
        section_contents={"file1.py": "content"},
        open_wires=[],
        closed_wires=[],
        target_path=".",
    )

    assert "report_path" in result
    assert "report_filename" in result
    assert os.path.exists(result["report_path"])

    # Passive report should contain the audit plan disclaimer
    with open(result["report_path"]) as f:
        content = f.read()
    assert "audit plan" in content.lower() or "documentation only" in content.lower()

    # Index updated
    index = manager.get_index()
    assert len(index["runs"]) == 1
    assert index["runs"][0]["type"] == "security"
    assert index["runs"][0]["mode"] == "passive"


def test_active_run_audit_uses_scanner(mock_llm, temp_output_dir, mock_scanner):
    # Triage call returns a valid JSON list; audit call returns a finding
    triage_response = json.dumps(
        [
            {"path": "app.py", "relevance": 0.9, "reason": "entry point"},
            {"path": "utils.py", "relevance": 0.7, "reason": "helper functions"},
        ]
    )
    mock_llm.call.side_effect = [
        {"answer": triage_response},  # Phase 1: triage
        {
            "answer": (
                "FINDING: SQL Injection\n"
                "Severity: HIGH\n"
                "File: app.py\n"
                "Line: 5\n"
                "Evidence: raw query\n"
                "Impact: data leak\n"
                "Fix: use parameterized queries"
            )
        },  # Phase 3: audit
    ]

    manager = AuditManager(mock_llm, temp_output_dir)
    result = manager.run_audit(
        audit_type="security",
        mode="active",
        section_contents={"app.py": "handles requests"},
        open_wires=[],
        closed_wires=[],
        target_path=mock_scanner.target_path,
        scanner=mock_scanner,
    )

    assert "report_path" in result
    assert os.path.exists(result["report_path"])

    # Scanner was called to discover and read files
    mock_scanner.get_all_files.assert_called_once()
    mock_scanner.read_file.assert_called()

    # Report contains files audited section
    with open(result["report_path"]) as f:
        content = f.read()
    assert "Files Audited" in content
    assert "app.py" in content

    # Index records files_audited count
    index = manager.get_index()
    assert index["runs"][0]["mode"] == "active"
    assert index["runs"][0]["files_audited"] == 2


def test_active_falls_back_to_passive_without_scanner(mock_llm, temp_output_dir):
    """Active mode with no scanner should gracefully fall back to passive."""
    manager = AuditManager(mock_llm, temp_output_dir)
    result = manager.run_audit(
        audit_type="security",
        mode="active",
        section_contents={"file1.py": "content"},
        open_wires=[],
        closed_wires=[],
        target_path=".",
        scanner=None,
    )

    assert "report_path" in result
    # One LLM call (passive path, not triage + audit)
    assert mock_llm.call.call_count == 1


def test_triage_handles_malformed_llm_json(mock_llm, temp_output_dir, mock_scanner):
    """Triage should fall back gracefully if LLM returns non-JSON."""
    mock_llm.call.side_effect = [
        {"answer": "Sorry, I cannot help with that."},  # bad triage response
        {"answer": "FINDING: Test\nSeverity: LOW\nFile: app.py\nLine: 1\nEvidence: x\nImpact: y\nFix: z"},
    ]

    manager = AuditManager(mock_llm, temp_output_dir)
    result = manager.run_audit(
        audit_type="security",
        mode="active",
        section_contents={},
        open_wires=[],
        closed_wires=[],
        target_path=mock_scanner.target_path,
        scanner=mock_scanner,
    )

    # Should still complete via fallback file selection
    assert "report_path" in result
    assert os.path.exists(result["report_path"])
