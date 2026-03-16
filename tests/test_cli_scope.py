"""Tests for scope filtering logic in codilay.cli.

The _file_matches_scope closure defined inside the `run` command uses fnmatch
and prefix-matching.  We replicate the exact logic here so we can test it
independently without having to invoke the full CLI pipeline.
"""

import fnmatch


def _file_matches_scope(rel_path: str, scope_patterns: list) -> bool:
    """Exact replica of the closure in cli.py run() — kept in sync by hand."""
    for pat in scope_patterns:
        norm = pat.rstrip("/")
        if fnmatch.fnmatch(rel_path, pat):
            return True
        if fnmatch.fnmatch(rel_path, pat.rstrip("/") + "/*"):
            return True
        # Plain prefix match (e.g. "src/auth" matches "src/auth/foo.py")
        if rel_path.startswith(norm + "/") or rel_path == norm:
            return True
    return False


# ── Exact match ───────────────────────────────────────────────────────────────


def test_exact_file_match():
    assert _file_matches_scope("src/auth.py", ["src/auth.py"]) is True


def test_exact_file_no_match():
    assert _file_matches_scope("src/payments.py", ["src/auth.py"]) is False


# ── Directory prefix match ────────────────────────────────────────────────────


def test_dir_prefix_matches_files_underneath():
    assert _file_matches_scope("src/auth/token.py", ["src/auth"]) is True
    assert _file_matches_scope("src/auth/sub/deep.py", ["src/auth"]) is True


def test_dir_prefix_trailing_slash_matches_files_underneath():
    assert _file_matches_scope("src/auth/token.py", ["src/auth/"]) is True


def test_dir_prefix_does_not_match_sibling_dirs():
    assert _file_matches_scope("src/payments/invoice.py", ["src/auth"]) is False


def test_dir_pattern_matches_exactly_named_file():
    """A pattern "src/auth" also matches a file literally named "src/auth"."""
    assert _file_matches_scope("src/auth", ["src/auth"]) is True


# ── Glob / fnmatch patterns ───────────────────────────────────────────────────


def test_glob_star_matches_any_file_in_dir():
    assert _file_matches_scope("src/auth/foo.py", ["src/auth/*"]) is True


def test_glob_extension_filter():
    assert _file_matches_scope("src/main.py", ["*.py"]) is True
    assert _file_matches_scope("src/main.js", ["*.py"]) is False


def test_glob_double_star_not_needed_for_prefix():
    """Prefix matching handles nested dirs without glob double-star."""
    assert _file_matches_scope("src/auth/v2/token.py", ["src/auth"]) is True


# ── Multiple patterns (OR logic) ──────────────────────────────────────────────


def test_multiple_patterns_any_match_succeeds():
    patterns = ["src/auth", "src/billing"]
    assert _file_matches_scope("src/auth/login.py", patterns) is True
    assert _file_matches_scope("src/billing/invoice.py", patterns) is True
    assert _file_matches_scope("src/analytics/track.py", patterns) is False


# ── Out-of-scope set derivation ───────────────────────────────────────────────


def test_out_of_scope_set_derived_correctly():
    all_files = [
        "src/auth/login.py",
        "src/billing/invoice.py",
        "src/analytics/track.py",
        "tests/test_auth.py",
    ]
    scope_patterns = ["src/auth", "src/billing"]

    in_scope = [f for f in all_files if _file_matches_scope(f, scope_patterns)]
    out_of_scope = set(f for f in all_files if not _file_matches_scope(f, scope_patterns))

    assert set(in_scope) == {"src/auth/login.py", "src/billing/invoice.py"}
    assert out_of_scope == {"src/analytics/track.py", "tests/test_auth.py"}


# ── out_of_scope wire classification logic ────────────────────────────────────
# The classification happens in _finalize_and_write but the same logic is
# exercised here in isolation: given open wires and an out_of_scope_set,
# split them into unresolved vs out-of-scope and verify the resulting
# DocStore section and links data.


def _classify_wires(open_wires, out_of_scope_set):
    """Exact replica of the wire-classification block in _finalize_and_write."""
    out_of_scope_wires = []
    unresolved_wires = []
    for w in open_wires:
        target_file = w.get("to", "")
        if target_file in out_of_scope_set:
            w = dict(w)
            w["status"] = "out-of-scope"
            out_of_scope_wires.append(w)
        else:
            unresolved_wires.append(w)
    return unresolved_wires, out_of_scope_wires


def test_wire_classification_separates_out_of_scope():
    open_wires = [
        {
            "id": "w1",
            "from": "src/auth.py",
            "to": "src/payments/client.py",
            "type": "import",
            "context": "PaymentClient",
        },
        {"id": "w2", "from": "src/auth.py", "to": "src/utils.py", "type": "call", "context": "helper"},
    ]
    out_of_scope_set = {"src/payments/client.py"}
    unresolved, out_of_scope = _classify_wires(open_wires, out_of_scope_set)

    assert len(out_of_scope) == 1
    assert out_of_scope[0]["to"] == "src/payments/client.py"
    assert out_of_scope[0]["status"] == "out-of-scope"

    assert len(unresolved) == 1
    assert unresolved[0]["to"] == "src/utils.py"
    assert "status" not in unresolved[0]


def test_wire_classification_empty_out_of_scope_set():
    open_wires = [
        {"id": "w1", "from": "a.py", "to": "b.py", "type": "import", "context": ""},
    ]
    unresolved, out_of_scope = _classify_wires(open_wires, set())
    assert len(unresolved) == 1
    assert len(out_of_scope) == 0


def test_wire_classification_all_out_of_scope():
    open_wires = [
        {"id": "w1", "from": "a.py", "to": "b.py", "type": "import", "context": ""},
        {"id": "w2", "from": "a.py", "to": "c.py", "type": "call", "context": ""},
    ]
    unresolved, out_of_scope = _classify_wires(open_wires, {"b.py", "c.py"})
    assert len(unresolved) == 0
    assert len(out_of_scope) == 2


def test_out_of_scope_docstore_section_created():
    from codilay.docstore import DocStore

    _, out_of_scope_wires = _classify_wires(
        [{"id": "w1", "from": "a.py", "to": "b.py", "type": "import", "context": "dep"}],
        {"b.py"},
    )

    ds = DocStore()
    ds.add_out_of_scope_references(out_of_scope_wires)
    assert "out-of-scope-references" in ds._sections


def test_out_of_scope_docstore_section_not_created_when_empty():
    from codilay.docstore import DocStore

    unresolved, out_of_scope_wires = _classify_wires(
        [{"id": "w1", "from": "a.py", "to": "b.py", "type": "import", "context": "dep"}],
        set(),  # nothing out of scope
    )

    ds = DocStore()
    ds.add_out_of_scope_references(out_of_scope_wires)
    assert "out-of-scope-references" not in ds._sections
