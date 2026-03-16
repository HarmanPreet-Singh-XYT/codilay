import os
import shutil
import tempfile
import pytest
from codilay.scanner import Scanner
from codilay.config import CodiLayConfig

@pytest.fixture
def temp_codebase():
    """Create a temporary codebase for testing."""
    temp_dir = tempfile.mkdtemp()
    
    # Create some files
    os.makedirs(os.path.join(temp_dir, "src/sub"))
    os.makedirs(os.path.join(temp_dir, "node_modules"))
    
    with open(os.path.join(temp_dir, "README.md"), "w") as f:
        f.write("# Test Project")
    
    with open(os.path.join(temp_dir, "src/main.py"), "w") as f:
        f.write("print('hello')")
        
    with open(os.path.join(temp_dir, "src/sub/utils.py"), "w") as f:
        f.write("def add(a, b): return a + b")
        
    with open(os.path.join(temp_dir, "node_modules/index.js"), "w") as f:
        f.write("console.log('ignored')")
        
    with open(os.path.join(temp_dir, ".gitignore"), "w") as f:
        f.write("ignored.txt\n*.tmp")
        
    with open(os.path.join(temp_dir, "ignored.txt"), "w") as f:
        f.write("should be ignored")
        
    with open(os.path.join(temp_dir, "test.tmp"), "w") as f:
        f.write("should be ignored")

    yield temp_dir
    shutil.rmtree(temp_dir)

def test_scanner_list_files(temp_codebase):
    config = CodiLayConfig(target_path=temp_codebase)
    scanner = Scanner(temp_codebase, config)
    
    files = scanner.get_all_files()
    
    # Check that basic files are present
    assert "README.md" in files
    assert "src/main.py" in files
    assert "src/sub/utils.py" in files
    
    # Check that ignored files/dirs are absent
    assert "node_modules/index.js" not in files
    assert "ignored.txt" not in files
    assert "test.tmp" not in files
    assert ".gitignore" in files  # Scanner marks .gitignore as a text file to include

def test_scanner_is_text_file(temp_codebase):
    config = CodiLayConfig(target_path=temp_codebase)
    scanner = Scanner(temp_codebase, config)
    
    assert scanner._is_text_file(os.path.join(temp_codebase, "src/main.py")) is True
    
    # Create a binary file
    bin_path = os.path.join(temp_codebase, "file.bin")
    with open(bin_path, "wb") as f:
        f.write(b"\x00\x01\x02\x03")
    
    assert scanner._is_text_file(bin_path) is False

def test_scanner_tree(temp_codebase):
    config = CodiLayConfig(target_path=temp_codebase)
    scanner = Scanner(temp_codebase, config)
    
    tree = scanner.get_file_tree()
    assert "README.md" in tree
    assert "src/" in tree
    assert "sub/" in tree
    assert "main.py" in tree
    assert "utils.py" in tree
    assert "node_modules" not in tree
