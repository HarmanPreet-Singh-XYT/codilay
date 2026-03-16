# Contributing to CodiLay

First off, thank you for considering contributing to CodiLay! It's people like you that make it a great tool.

## Code of Conduct

By participating in this project, you agree to abide by our code of conduct (see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) if available).

## How Can I Contribute?

### Reporting Bugs

- Use the GitHub issue tracker to report bugs.
- Provide a clear and concise description of the bug.
- Include steps to reproduce the issue.
- Mention your OS, Python version, and the LLM provider you were using.

### Suggesting Enhancements

- Enhancements are welcome! Open an issue with the "feature request" label.
- Explain why the enhancement would be useful and how you imagine it working.

### Pull Requests

1.  **Fork the repository** and create your branch from `main`.
2.  **Install development dependencies**:
    ```bash
    pip install -e ".[dev]"
    ```
3.  **Ensure tests pass**:
    ```bash
    pytest
    ```
4.  **Follow the codebase style**:
    - Use `ruff` for linting and formatting.
    - Keep functions small and focused.
    - Use type hints wherever possible.
5.  **Write clear commit messages**:
    - `feat: add support for Grok-1`
    - `fix: resolve issue with large file chunking`
    - `docs: update installation instructions in README`

## Project Architecture & The Wire Model

Before contributing to the core logic, please read the "Core Concept — The Wire Model" section in the [README.md](README.md). This is the fundamental abstraction of the system.

- **Wires** are managed in `src/codilay/wire_manager.py`.
- **LLM Clients** are in `src/codilay/llm_client.py`.
- **The processing loop** is in `src/codilay/processor.py`.

## Development Setup

We use `pip install -e .` for editable installs. 

```bash
git clone https://github.com/HarmanPreet-Singh-XYT/codilay.git
cd codilay
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Happy coding!
