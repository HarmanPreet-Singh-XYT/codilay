from unittest.mock import MagicMock

import pytest

from codilay.config import CodiLayConfig
from codilay.processor import Processor
from codilay.state import AgentState


@pytest.fixture
def mock_deps():
    llm = MagicMock()
    llm.count_tokens.return_value = 100
    llm.call.return_value = {
        "new_section": {
            "id": "test-file",
            "title": "Test File",
            "content": "Test content",
            "tags": ["test"],
        },
        "wires_opened": [],
        "wires_closed": [],
    }

    config = CodiLayConfig()
    wire_mgr = MagicMock()
    wire_mgr.find_wires_to.return_value = []
    wire_mgr.get_open_wires.return_value = []
    wire_mgr.reprioritize_queue.side_effect = lambda q: q

    docstore = MagicMock()
    docstore.get_relevant_sections.return_value = {}
    docstore.get_section_index.return_value = {}
    docstore.get_section_contents.return_value = {}

    state = AgentState()
    ui = MagicMock()

    return llm, config, wire_mgr, docstore, state, ui


def test_processor_single_pass(mock_deps):
    llm, config, wire_mgr, docstore, state, ui = mock_deps
    processor = Processor(llm, config, wire_mgr, docstore, state, ui)

    result = processor.process_file("src/test.py", "print('hello')")

    assert result is not None
    assert llm.call.called
    docstore.add_section.assert_called_once()
    ui.file_processed.assert_called_once()


def test_processor_apply_result_wires(mock_deps):
    llm, config, wire_mgr, docstore, state, ui = mock_deps
    processor = Processor(llm, config, wire_mgr, docstore, state, ui)

    result = {
        "wires_opened": [{"to": "other.py", "type": "import", "context": "import other"}],
        "wires_closed": ["wire-123"],
    }

    processor._apply_result("src/test.py", result, [])

    wire_mgr.close_wires_by_ids.assert_called_with(["wire-123"], resolved_in="src/test.py")
    wire_mgr.open_wire.assert_called_with(
        from_file="src/test.py",
        to_target="other.py",
        wire_type="import",
        context="import other",
    )


def test_processor_path_to_id(mock_deps):
    processor = Processor(*mock_deps)
    assert processor._path_to_id("src/codilay/processor.py") == "codilay-processor"
    assert processor._path_to_id("lib/utils.js") == "utils"
    assert processor._path_to_id("main.py") == "main"


def test_processor_extract_imports(mock_deps):
    processor = Processor(*mock_deps)
    content = """
    import os
    from sys import path
    import requests
    from .local import thing
    """
    imports = processor._extract_imports(content, "test.py")
    assert "os" in imports
    assert "sys" in imports
    assert "requests" in imports
