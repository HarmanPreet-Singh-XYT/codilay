import pytest
from codilay.chunker import Chunker, ChunkType
from codilay.config import CodiLayConfig

@pytest.fixture
def chunker():
    def mock_token_counter(text):
        # Rough token count: 1 per word
        return len(text.split())
    config = CodiLayConfig()
    config.chunk_token_threshold = 10
    config.max_chunk_tokens = 5
    return Chunker(mock_token_counter, config)

def test_chunker_small_file():
    def mock_token_counter(text):
        return len(text.split())
    config = CodiLayConfig()
    config.chunk_token_threshold = 100
    c = Chunker(mock_token_counter, config)
    
    content = "This is a small file."
    plan = c.plan("test.py", content)
    
    assert not plan.needs_chunking
    assert len(plan.chunks) == 1
    assert plan.chunks[0].chunk_type == ChunkType.FULL

def test_chunker_large_file(chunker):
    content = """
import os

class MyClass:
    def __init__(self):
        print("init")
        print("more code")
        print("even more code to make it long")

    def method_one(self):
        print("one")
        print("two")
        print("three")

def top_level_func():
    print("top")
    print("bottom")
    """
    plan = chunker.plan("test.py", content)
    
    assert plan.needs_chunking
    assert plan.skeleton is not None
    assert "class MyClass" in plan.skeleton.content
    # Depending on exact splitting, we should have a few chunks
    assert len(plan.chunks) >= 1

def test_chunker_python_boundaries():
    def mock_token_counter(text): return 0
    c = Chunker(mock_token_counter, CodiLayConfig())
    content = """
class A:
    def inner(self):
        pass

def b():
    pass
    """
    lines = content.split('\n')
    boundaries = c._find_python_boundaries(lines)
    
    assert len(boundaries) == 2
    assert boundaries[0]['label'] == "class A"
    assert boundaries[1]['label'] == "function b"

def test_chunker_js_boundaries():
    def mock_token_counter(text): return 0
    c = Chunker(mock_token_counter, CodiLayConfig())
    content = """
export class UserService {
}

function getData() {
}
    """
    lines = content.split('\n')
    boundaries = c._find_js_boundaries(lines)
    
    assert len(boundaries) == 2
    assert "class UserService" in boundaries[0]['label']
    assert "function getData" in boundaries[1]['label']
