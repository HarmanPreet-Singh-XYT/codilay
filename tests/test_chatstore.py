import pytest
import shutil
import tempfile
from codilay.chatstore import ChatStore, make_message

@pytest.fixture
def chat_store():
    tmpdir = tempfile.mkdtemp()
    store = ChatStore(tmpdir)
    yield store
    shutil.rmtree(tmpdir)

def test_chatstore_create_list(chat_store):
    conv = chat_store.create_conversation("Test Convo")
    assert conv["title"] == "Test Convo"
    assert "id" in conv
    
    convs = chat_store.list_conversations()
    assert len(convs) == 1
    assert convs[0]["id"] == conv["id"]

def test_chatstore_add_message(chat_store):
    conv = chat_store.create_conversation("")
    msg = make_message("user", "Hello world")
    chat_store.add_message(conv["id"], msg)
    
    updated = chat_store.get_conversation(conv["id"])
    assert len(updated["messages"]) == 1
    assert updated["messages"][0]["content"] == "Hello world"
    # Auto-title check
    assert updated["title"] == "Hello world"

def test_chatstore_edit_message(chat_store):
    conv = chat_store.create_conversation("Title")
    chat_store.add_message(conv["id"], make_message("user", "m1"))
    m2 = make_message("assistant", "m2")
    chat_store.add_message(conv["id"], m2)
    chat_store.add_message(conv["id"], make_message("user", "m3"))
    
    # Edit m2
    chat_store.edit_message(conv["id"], m2["id"], "new m2")
    
    updated = chat_store.get_conversation(conv["id"])
    assert len(updated["messages"]) == 2
    assert updated["messages"][1]["content"] == "new m2"
    # m3 (index 2) should be gone due to truncation
    assert len(updated["messages"]) == 2

def test_chatstore_memory(chat_store):
    chat_store.add_memory_fact("The user likes Python")
    mem = chat_store.load_memory()
    assert len(mem["facts"]) == 1
    assert mem["facts"][0]["fact"] == "The user likes Python"
    
    ctx = chat_store.build_memory_context()
    assert "The user likes Python" in ctx

def test_chatstore_pinning(chat_store):
    conv = chat_store.create_conversation("Convo")
    m1 = make_message("assistant", "answer")
    chat_store.add_message(conv["id"], m1)
    
    chat_store.pin_message(conv["id"], m1["id"], True)
    pinned = chat_store.get_pinned_messages(conv["id"])
    assert len(pinned) == 1
    assert pinned[0]["content"] == "answer"
