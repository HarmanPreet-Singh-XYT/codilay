from unittest.mock import MagicMock
from codilay.planner import Planner
from codilay.config import CodiLayConfig
from codilay.state import AgentState

def test_planner_plan_validation():
    # Mock LLM client
    llm = MagicMock()
    llm.call.return_value = {
        "order": ["src/main.py"],
        "parked": ["src/complex.py"],
        "park_reasons": {"src/complex.py": "Waiting for dependencies"},
        "skeleton": {
            "doc_title": "Custom Title",
            "suggested_sections": ["S1", "S2"]
        }
    }
    
    config = CodiLayConfig()
    planner = Planner(llm, config)
    
    files = ["src/main.py", "src/complex.py", "README.md"]
    state = AgentState()
    
    plan = planner.plan("tree", {}, files, state)
    
    assert plan["order"] == ["src/main.py", "README.md"] # README.md was missing from order, so appended
    assert plan["parked"] == ["src/complex.py"]
    assert plan["skeleton"]["doc_title"] == "Custom Title"
    assert "S1" in plan["skeleton"]["suggested_sections"]

def test_planner_invalid_response_recovery():
    llm = MagicMock()
    llm.call.return_value = {"something": "else"} # Missing order, parked, etc.
    
    config = CodiLayConfig()
    planner = Planner(llm, config)
    
    files = ["a.py", "b.py"]
    state = AgentState()
    
    plan = planner.plan("tree", {}, files, state)
    
    assert set(plan["order"]) == set(files)
    assert plan["parked"] == []
    assert "doc_title" in plan["skeleton"]
    assert len(plan["skeleton"]["suggested_sections"]) > 0
