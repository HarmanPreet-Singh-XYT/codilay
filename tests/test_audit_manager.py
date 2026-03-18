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
    llm.call.return_value = {"answer": "FINDING: Test Finding\nSeverity: HIGH\nEvidence: Test"}
    return llm


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


def test_build_prompt(mock_llm, temp_output_dir):
    manager = AuditManager(mock_llm, temp_output_dir)
    prompt = manager._build_prompt(
        audit_type="security", mode="passive", sections={"file1.py": "def test(): pass"}, open_wires=[], closed_wires=[]
    )
    assert "Run a PASSIVE audit" in prompt
    assert "vulnerabilities" in prompt.lower()
    assert "file1.py" in prompt


def test_run_audit(mock_llm, temp_output_dir):
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
    assert result["response"] == "FINDING: Test Finding\nSeverity: HIGH\nEvidence: Test"

    # Check if report file exists
    assert os.path.exists(result["report_path"])

    # Check if index was updated
    index = manager.get_index()
    assert len(index["runs"]) == 1
    assert index["runs"][0]["type"] == "security"
