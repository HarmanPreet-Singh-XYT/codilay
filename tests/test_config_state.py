import os
import json
import tempfile
import shutil
import pytest
from codilay.config import CodiLayConfig
from codilay.state import AgentState

def test_config_load_default():
    # No config file
    with tempfile.TemporaryDirectory() as tmpdir:
        config = CodiLayConfig.load(tmpdir)
        assert config.target_path == tmpdir
        assert config.llm_provider == "anthropic"
        assert config.llm_model is None

def test_config_load_from_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_data = {
            "llm": {
                "provider": "openai",
                "model": "gpt-4o"
            },
            "ignore": ["data/", "*.log"],
            "triage": "fast"
        }
        config_path = os.path.join(tmpdir, "codilay.config.json")
        with open(config_path, "w") as f:
            json.dump(config_data, f)
            
        config = CodiLayConfig.load(tmpdir)
        assert config.llm_provider == "openai"
        assert config.llm_model == "gpt-4o"
        assert "data/" in config.ignore_patterns
        assert config.triage_mode == "fast"

def test_agent_state_save_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = os.path.join(tmpdir, "state.json")
        state = AgentState(run_id="test-run")
        state.queue = ["a.py", "b.py"]
        state.processed = ["README.md"]
        state.open_wires = [{"id": "w1", "from": "a.py", "to": "b.py"}]
        
        state.save(state_path)
        assert os.path.exists(state_path)
        
        loaded = AgentState.load(state_path)
        assert loaded.run_id == "test-run"
        assert loaded.queue == ["a.py", "b.py"]
        assert loaded.processed == ["README.md"]
        assert len(loaded.open_wires) == 1
        assert loaded.open_wires[0]["id"] == "w1"
