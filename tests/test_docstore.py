import pytest
from codilay.docstore import DocStore

def test_docstore_skeleton():
    ds = DocStore()
    ds.initialize_skeleton("Test Doc", ["Section A", "Section B"])
    
    assert ds._doc_title == "Test Doc"
    assert "overview" in ds._sections
    assert "section-a" in ds._sections
    assert "section-b" in ds._sections
    assert ds._sections["overview"]["title"] == "Overview"

def test_docstore_add_patch():
    ds = DocStore()
    ds.add_section("sec1", "Title 1", "Content 1")
    assert ds._sections["sec1"]["content"] == "Content 1"
    
    ds.patch_section("sec1", "append", "More Content")
    assert ds._sections["sec1"]["content"] == "Content 1\n\nMore Content"
    
    ds.patch_section("sec1", "replace", "New Content")
    assert ds._sections["sec1"]["content"] == "New Content"

def test_docstore_relevant_sections():
    ds = DocStore()
    ds.add_section("overview", "Overview", "Project overview")
    ds.add_section("sec1", "Section 1", "Deeper content", file="src/main.py")
    ds.add_section("sec2", "Section 2", "Other content", file="src/utils.py", deps=["src/main.py"])
    
    # Overview should always be relevant if not empty
    relevant = ds.get_relevant_sections("src/main.py")
    assert "overview" in relevant
    assert "sec1" in relevant
    assert "sec2" in relevant # Because it depends on main.py

def test_docstore_render():
    ds = DocStore()
    ds.initialize_skeleton("Project Doc", [])
    ds.patch_section("overview", "replace", "This is the overview.")
    ds.add_section("sec1", "Features", "- Feature 1\n- Feature 2", file="features.txt")
    
    doc = ds.render_full_document()
    assert "# Project Doc" in doc
    assert "## Overview" in doc
    assert "This is the overview." in doc
    assert "## Features" in doc
    assert "- Feature 1" in doc

def test_docstore_slugify():
    ds = DocStore()
    assert ds._slugify("Hello World!") == "hello-world"
    assert ds._slugify("My_File_Name") == "my-file-name"
    assert ds._slugify("   Extra  Spaces  ") == "extra-spaces"
