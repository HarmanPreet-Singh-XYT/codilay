from codilay.triage import Triage


def test_fast_triage():
    files = [
        "src/main.py",
        "node_modules/express/index.js",
        "README.md",
        "pyproject.toml",
        "dist/bundle.js",
        "src/generated/api.g.dart",
    ]
    triage = Triage()
    result = triage.fast_triage(files)

    assert "src/main.py" in result.core
    assert "node_modules/express/index.js" in result.skip
    assert "pyproject.toml" in result.skim
    assert "dist/bundle.js" in result.skip
    # Handle compound extensions
    assert "src/generated/api.g.dart" in result.skip


def test_triage_project_detection():
    triage = Triage()
    assert triage._detect_project_type(["go.mod", "main.go"]) == "go"
    assert triage._detect_project_type(["Cargo.toml", "src/main.rs"]) == "rust"
    assert triage._detect_project_type(["manage.py", "app/views.py"]) == "django"


def test_expand_patterns():
    triage = Triage()
    files = ["src/a.py", "src/b.py", "lib/c.js", "README.md"]

    # Directory pattern
    expanded = triage._expand_patterns(["src/"], files)
    assert "src/a.py" in expanded
    assert "src/b.py" in expanded

    # Glob
    expanded = triage._expand_patterns(["src/*.py"], files)
    assert "src/a.py" in expanded
    assert "src/b.py" in expanded

    # Basename
    expanded = triage._expand_patterns(["c.js"], files)
    assert "lib/c.js" in expanded


def test_apply_safety_net():
    triage = Triage()
    from codilay.triage import TriageResult

    result = TriageResult(core=["src/main.py", "node_modules/bad.js"])
    triage._apply_safety_net(result)

    assert "src/main.py" in result.core
    assert "node_modules/bad.js" in result.skip
    assert "node_modules/bad.js" not in result.core
