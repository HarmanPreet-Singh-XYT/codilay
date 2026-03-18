"""
Export Specification — defines how to customize AI context exports.

An ExportSpec encodes what to include, what to exclude, and how much detail
to preserve when exporting CodiLay documentation for LLM context injection.

This allows users to request specific slices of their documentation
(e.g., "just file structure", "auth module with dependencies", etc.)
instead of always exporting the full compressed doc.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExportSpec:
    """
    Specification for customizing documentation export.

    This defines which sections to include/exclude, what level of detail
    to preserve, and what content transformations to apply.
    """

    # Sections to include (by section ID or pattern)
    # Empty list = include all sections
    include_sections: List[str] = field(default_factory=list)

    # Sections to explicitly exclude (takes precedence over include)
    exclude_sections: List[str] = field(default_factory=list)

    # Whether to include dependency graph
    include_graph: bool = True

    # Whether to include unresolved references
    include_unresolved: bool = False

    # Whether to strip implementation details (keep only signatures/interfaces)
    strip_implementation: bool = False

    # Content elements to keep
    keep: List[str] = field(
        default_factory=lambda: [
            "function signatures",
            "cross-links",
            "file paths",
            "section headers",
        ]
    )

    # Content elements to strip
    strip: List[str] = field(default_factory=list)

    # Human-readable summary of what this spec does
    summary: str = "Full documentation export"

    # Maximum token budget (None = no limit)
    max_tokens: Optional[int] = None

    # Output format
    format: str = "markdown"  # markdown | xml | json

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportSpec":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def matches_section(self, section_id: str) -> bool:
        """
        Check if a section should be included based on this spec.

        Args:
            section_id: Section identifier to check

        Returns:
            True if the section should be included
        """
        # Explicit exclusion takes precedence
        if section_id in self.exclude_sections:
            return False

        # Check exclusion patterns
        for pattern in self.exclude_sections:
            if pattern.endswith("*") and section_id.startswith(pattern[:-1]):
                return False

        # If include list is empty, include everything (except excluded)
        if not self.include_sections:
            return True

        # Check explicit inclusion
        if section_id in self.include_sections:
            return True

        # Check inclusion patterns
        for pattern in self.include_sections:
            if pattern.endswith("*") and section_id.startswith(pattern[:-1]):
                return True

        return False


# ── Built-in presets ──────────────────────────────────────────────────────────


BUILTIN_PRESETS: Dict[str, ExportSpec] = {
    "structure": ExportSpec(
        include_sections=["overview", "entry-point", "routes", "models"],
        include_graph=True,
        include_unresolved=False,
        strip_implementation=True,
        keep=["file paths", "cross-links", "section headers"],
        strip=["function bodies", "code examples", "detailed explanations"],
        summary="File structure and linkage map — no implementation detail",
        max_tokens=3000,
    ),
    "api-surface": ExportSpec(
        include_sections=["routes", "api", "endpoints", "models", "schemas"],
        include_graph=True,
        include_unresolved=False,
        strip_implementation=False,
        keep=["function signatures", "request/response schemas", "route definitions"],
        strip=["internal implementation", "helper functions"],
        summary="Public API surface with request/response schemas",
        max_tokens=5000,
    ),
    "onboarding": ExportSpec(
        include_sections=["overview", "entry-point", "setup", "architecture"],
        include_graph=False,
        include_unresolved=False,
        strip_implementation=True,
        keep=["high-level architecture", "entry points", "setup instructions"],
        strip=["implementation details", "internal utilities"],
        summary="High-level overview for project onboarding",
        max_tokens=2000,
    ),
    "dependencies-only": ExportSpec(
        include_sections=[],
        exclude_sections=["*"],
        include_graph=True,
        include_unresolved=True,
        strip_implementation=True,
        summary="Dependency graph only — no section content",
        max_tokens=1000,
    ),
}


def get_preset(name: str, custom_presets: Optional[Dict[str, Dict]] = None) -> Optional[ExportSpec]:
    """
    Get a preset by name from built-in or custom presets.

    Args:
        name: Preset name
        custom_presets: Optional dictionary of custom preset definitions

    Returns:
        ExportSpec if found, None otherwise
    """
    # Check custom presets first
    if custom_presets and name in custom_presets:
        return ExportSpec.from_dict(custom_presets[name])

    # Fall back to built-in presets
    return BUILTIN_PRESETS.get(name)


def list_presets(custom_presets: Optional[Dict[str, Dict]] = None) -> List[tuple[str, str]]:
    """
    List all available presets with their summaries.

    Args:
        custom_presets: Optional dictionary of custom preset definitions

    Returns:
        List of (name, summary) tuples
    """
    presets = []

    # Built-in presets
    for name, spec in BUILTIN_PRESETS.items():
        presets.append((name, spec.summary))

    # Custom presets
    if custom_presets:
        for name, data in custom_presets.items():
            summary = data.get("summary", "Custom preset")
            presets.append((f"{name} (custom)", summary))

    return presets
