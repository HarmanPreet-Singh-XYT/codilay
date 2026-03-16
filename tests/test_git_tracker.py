import pytest
import os
import shutil
import tempfile
import subprocess
from codilay.git_tracker import GitTracker, ChangeType

@pytest.fixture
def repo():
    tmpdir = tempfile.mkdtemp()
    subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmpdir)
    
    # Need at least one commit for HEAD to exist
    with open(os.path.join(tmpdir, "file1.py"), "w") as f:
        f.write("print('hello')")
    
    subprocess.run(["git", "add", "."], cwd=tmpdir)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmpdir)
    
    yield tmpdir
    shutil.rmtree(tmpdir)

def test_git_tracker_is_repo(repo):
    tracker = GitTracker(repo)
    assert tracker.is_git_repo

def test_git_tracker_get_commit(repo):
    tracker = GitTracker(repo)
    commit = tracker.get_current_commit()
    assert commit is not None
    assert len(commit) == 40

def test_git_tracker_diff(repo):
    tracker = GitTracker(repo)
    base_commit = tracker.get_current_commit()
    
    # Modify file
    with open(os.path.join(repo, "file1.py"), "a") as f:
        f.write("\nprint('world')")
        
    # Add new file
    with open(os.path.join(repo, "file2.py"), "w") as f:
        f.write("new file")
        
    subprocess.run(["git", "add", "."], cwd=repo)
    subprocess.run(["git", "commit", "-m", "Second commit"], cwd=repo)
    
    diff = tracker.get_diff(base_commit)
    assert diff is not None
    assert diff.commits_behind == 1
    assert len(diff.changes) == 2
    
    modified = [c for c in diff.changes if c.change_type == ChangeType.MODIFIED]
    added = [c for c in diff.changes if c.change_type == ChangeType.ADDED]
    
    assert len(modified) == 1
    assert modified[0].path == "file1.py"
    assert len(added) == 1
    assert added[0].path == "file2.py"

def test_git_tracker_parse_name_status():
    # Use any directory that is a repo or just mock it, but here we can just use current dir
    tracker = GitTracker(os.getcwd()) 
    output = "M\tfile1.py\nA\tfile2.py\nD\tfile3.py\nR100\told.py\tnew.py"
    changes = tracker._parse_name_status(output)
    
    assert len(changes) == 4
    assert changes[0].change_type == ChangeType.MODIFIED
    assert changes[1].change_type == ChangeType.ADDED
    assert changes[2].change_type == ChangeType.DELETED
    assert changes[3].change_type == ChangeType.RENAMED
    assert changes[3].old_path == "old.py"
    assert changes[3].path == "new.py"

def test_git_tracker_uncommitted(repo):
    tracker = GitTracker(repo)
    
    with open(os.path.join(repo, "uncommitted.py"), "w") as f:
        f.write("content")
        
    uncommitted = tracker.get_uncommitted_changes()
    assert len(uncommitted) == 1
    assert uncommitted[0].path == "uncommitted.py"
    assert uncommitted[0].change_type == ChangeType.ADDED
