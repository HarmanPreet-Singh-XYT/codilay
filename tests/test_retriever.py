from codilay.retriever import Retriever, _tokenize

def test_tokenize():
    text = "getUserById with snake_case and CamelCase. Also stop words like 'the'."
    tokens = _tokenize(text)
    assert "get" in tokens
    assert "user" in tokens
    assert "id" in tokens
    assert "snake" in tokens
    assert "case" in tokens
    assert "camel" in tokens
    assert "the" not in tokens

def test_retriever_search():
    index = {
        "sec1": {"title": "Auth System", "file": "src/auth.py", "tags": ["login", "security"]},
        "sec2": {"title": "Database", "file": "src/db.py", "tags": ["sql", "storage"]}
    }
    contents = {
        "sec1": "This handles user authentication and session management.",
        "sec2": "This handles database connections and SQL queries."
    }
    
    retriever = Retriever(index, contents)
    
    # Search for auth
    results = retriever.search("how does authentication work?")
    assert len(results) > 0
    assert results[0].section_id == "sec1"
    
    # Search for db
    results = retriever.search("sql queries")
    assert len(results) > 0
    assert results[0].section_id == "sec2"

def test_retriever_search_by_file():
    index = {
        "sec1": {"title": "Auth", "file": "src/auth.py", "tags": []},
        "sec2": {"title": "DB", "file": "src/db.py", "tags": []}
    }
    contents = {"sec1": "auth content", "sec2": "db content"}
    retriever = Retriever(index, contents)
    
    results = retriever.search_by_file("src/auth.py")
    assert len(results) == 1
    assert results[0].section_id == "sec1"

def test_retriever_build_context():
    index = {
        "sec1": {"title": "Architecture Overview", "file": "arch.py", "tags": []},
        "sec2": {"title": "Database Schema", "file": "db.py", "tags": []}
    }
    contents = {
        "sec1": "This is a very long architecture description word " * 100,
        "sec2": "Database stuff"
    }
    
    retriever = Retriever(index, contents)
    
    def mock_token_counter(text):
        return len(text.split())
        
    # Budget of 300 tokens
    context = retriever.build_context("Architecture", mock_token_counter, token_budget=300)
    assert "Overview" in context
    assert "[truncated]" in context

def test_retriever_get_source_files():
    index = {
        "sec1": {"title": "Auth", "file": "auth.py", "tags": []},
        "sec2": {"title": "DB", "file": "db.py", "tags": []}
    }
    contents = {"sec1": "auth", "sec2": "db"}
    retriever = Retriever(index, contents)
    
    files = retriever.get_source_files("auth system")
    assert "auth.py" in files
    assert len(files) >= 1
