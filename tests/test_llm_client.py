import pytest
import os
from unittest.mock import MagicMock, patch
from codilay.llm_client import LLMClient
from codilay.config import CodiLayConfig

@pytest.fixture
def mock_config():
    config = CodiLayConfig()
    config.llm_provider = "openai"
    config.llm_model = "gpt-4o"
    return config

@patch('openai.OpenAI')
def test_llm_client_openai_call(mock_openai, mock_config):
    os.environ["OPENAI_API_KEY"] = "test-key"
    client = LLMClient(mock_config)
    
    # Mock response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"answer": "hello"}'
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    mock_openai.return_value.chat.completions.create.return_value = mock_response
    
    result = client.call("sys", "user")
    assert result == {"answer": "hello"}
    assert client.total_input_tokens == 10
    assert client.total_output_tokens == 5

@patch('anthropic.Anthropic')
def test_llm_client_anthropic_call(mock_anthropic, mock_config):
    mock_config.llm_provider = "anthropic"
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    client = LLMClient(mock_config)
    
    # Mock response
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = '{"answer": "hi"}'
    mock_response.usage.input_tokens = 20
    mock_response.usage.output_tokens = 10
    mock_anthropic.return_value.messages.create.return_value = mock_response
    
    result = client.call("sys", "user")
    assert result == {"answer": "hi"}

def test_llm_client_parse_json(mock_config):
    with patch('openai.OpenAI'):
        client = LLMClient(mock_config)
        
        # Test markdown stripping
        res = client._parse_json("```json\n{\"id\": 1}\n```")
        assert res == {"id": 1}
        
        # Test simple parsing
        res = client._parse_json("{\"id\": 2}")
        assert res == {"id": 2}

def test_llm_client_salvage_json(mock_config):
    with patch('openai.OpenAI'):
        client = LLMClient(mock_config)
        
        # Test salvage
        res = client._salvage_json("Here is the json: {\"foo\": \"bar\"} hope you like it")
        assert res == {"foo": "bar"}
        
        # Test salvage failure
        res = client._salvage_json("no json here")
        assert "error" in res
