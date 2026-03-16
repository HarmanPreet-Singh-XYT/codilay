from codilay.wire_manager import WireManager

def test_wire_lifecycle():
    wm = WireManager()
    
    # Open some wires
    w1 = wm.open_wire("src/main.py", "src/utils.py", "import", "Importing utils")
    w2 = wm.open_wire("src/main.py", "Logger", "reference", "Using logger")
    
    assert len(wm.get_open_wires()) == 2
    assert w1["id"] == "wire_000"
    assert w2["id"] == "wire_001"
    
    # Close a wire
    wm.close_wire("wire_000", "src/utils.py", "Resolved by doc in utils.py")
    
    assert len(wm.get_open_wires()) == 1
    assert len(wm.get_closed_wires()) == 1
    assert wm.get_closed_wires()[0]["id"] == "wire_000"
    assert wm.get_closed_wires()[0]["resolved_in"] == "src/utils.py"

def test_find_wires():
    wm = WireManager()
    wm.open_wire("src/a.py", "src/b.py", "call")
    wm.open_wire("src/c.py", "src/b.py", "call")
    wm.open_wire("src/a.py", "src/d.py", "call")
    
    # Find wires to src/b.py
    to_b = wm.find_wires_to("src/b.py")
    assert len(to_b) == 2
    
    # Find wires from src/a.py
    from_a = wm.find_wires_from("src/a.py")
    assert len(from_a) == 2

def test_reopen_wires_for_changed_files():
    wm = WireManager()
    wm.open_wire("src/a.py", "src/b.py", "call")
    wm.close_wire("wire_000", "src/b.py", "Resolved")
    
    assert len(wm.get_open_wires()) == 0
    assert len(wm.get_closed_wires()) == 1
    
    # src/a.py changed, should reopen wire_000
    reopened = wm.reopen_wires_for_files(["src/a.py"])
    assert reopened == 1
    assert len(wm.get_open_wires()) == 1
    assert len(wm.get_closed_wires()) == 0
    assert "resolved_in" not in wm.get_open_wires()[0]

def test_handle_renamed_file():
    wm = WireManager()
    wm.open_wire("src/old.py", "target.py", "call")
    wm.open_wire("other.py", "src/old.py", "call")
    
    updated = wm.handle_renamed_file("src/old.py", "src/new.py")
    assert updated == 2
    
    open_wires = wm.get_open_wires()
    assert open_wires[0]["from"] == "src/new.py"
    assert open_wires[1]["to"] == "src/new.py"

def test_handle_deleted_file():
    wm = WireManager()
    wm.open_wire("src/deleted.py", "target.py", "call")
    wm.open_wire("other.py", "src/deleted.py", "call")
    
    result = wm.handle_deleted_file("src/deleted.py")
    assert "wire_000" in result["orphaned_from"]
    assert "wire_001" in result["orphaned_to"]
    
    open_wires = wm.get_open_wires()
    assert "[SOURCE DELETED]" in open_wires[0]["context"]
    assert "[TARGET DELETED]" in open_wires[1]["context"]
