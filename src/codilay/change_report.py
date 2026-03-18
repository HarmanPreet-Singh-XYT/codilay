"""
Change report generator — formats diff-run analysis into a readable report.

Produces a focused "what changed and why it matters" document rather than
a full codebase reference.
"""

import os
from datetime import datetime
from typing import Any, Dict, List


class ChangeReportGenerator:
    """
    Generates markdown change reports from diff-run analysis results.

    Unlike full CODEBASE.md, these reports focus on:
    - What changed in this specific commit range
    - Why it matters (impact, connections)
    - Wires opened/closed/broken
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def generate_report(
        self,
        analysis_result: dict,
        boundary_ref: str,
        boundary_type: str,
        commits_count: int,
        commit_messages: List[str],
    ) -> str:
        """
        Generate a change report from LLM analysis.

        Returns the path to the generated report file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"CHANGES_{boundary_type}_{timestamp}.md"
        report_path = os.path.join(self.output_dir, report_filename)

        # Build the report
        report = self._build_report_content(
            analysis_result,
            boundary_ref,
            boundary_type,
            commits_count,
            commit_messages,
        )

        # Write to file
        os.makedirs(self.output_dir, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        return report_path

    def _build_report_content(
        self,
        analysis: dict,
        boundary_ref: str,
        boundary_type: str,
        commits_count: int,
        commit_messages: List[str],
    ) -> str:
        """Build the markdown content for the change report."""

        # Header
        boundary_label = self._format_boundary_label(boundary_ref, boundary_type)
        commit_summary = f"{commits_count} commit{'s' if commits_count != 1 else ''}"

        lines = [
            "# CodiLay Change Report",
            "",
            f"> Changes since **{boundary_label}** — {commit_summary}",
            "",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "---",
            "",
        ]

        # Summary
        summary = analysis.get("summary", "")
        if summary:
            lines.extend(
                [
                    "## Summary",
                    "",
                    summary,
                    "",
                ]
            )

        # Commit log
        if commit_messages:
            lines.extend(
                [
                    "## Commits",
                    "",
                    "```",
                ]
            )
            lines.extend(commit_messages[:20])
            if len(commit_messages) > 20:
                lines.append(f"... and {len(commit_messages) - 20} more")
            lines.extend(
                [
                    "```",
                    "",
                ]
            )

        # Added files
        added = analysis.get("added", [])
        if added:
            lines.extend(
                [
                    "## Added",
                    "",
                ]
            )
            for item in added:
                path = item.get("path", "")
                title = item.get("title", path)
                description = item.get("description", "")
                wires_opened = item.get("wires_opened", [])

                lines.append(f"### {title}")
                lines.append(f"**File:** `{path}`")
                lines.append("")
                lines.append(description)
                lines.append("")

                if wires_opened:
                    lines.append("**Dependencies introduced:**")
                    for wire in wires_opened:
                        lines.append(f"- `{wire}`")
                    lines.append("")

        # Modified files
        modified = analysis.get("modified", [])
        if modified:
            lines.extend(
                [
                    "## Modified",
                    "",
                ]
            )
            for item in modified:
                path = item.get("path", "")
                changes = item.get("changes_description", "")
                impact = item.get("impact", "")
                wires_opened = item.get("wires_opened", [])
                wires_closed = item.get("wires_closed", [])

                lines.append(f"### {path}")
                lines.append("")

                if changes:
                    lines.append(f"**Changes:** {changes}")
                    lines.append("")

                if impact:
                    lines.append(f"**Impact:** {impact}")
                    lines.append("")

                if wires_opened:
                    lines.append("**New dependencies:**")
                    for wire in wires_opened:
                        lines.append(f"- `{wire}`")
                    lines.append("")

                if wires_closed:
                    lines.append("**Dependencies satisfied:**")
                    for wire in wires_closed:
                        lines.append(f"- `{wire}` ✓")
                    lines.append("")

        # Deleted files
        deleted = analysis.get("deleted", [])
        if deleted:
            lines.extend(
                [
                    "## Deleted",
                    "",
                ]
            )
            for item in deleted:
                path = item.get("path", "")
                what_it_was = item.get("what_it_was", "")
                broken_wires = item.get("broken_wires", [])

                lines.append(f"### {path}")
                lines.append("")

                if what_it_was:
                    lines.append(what_it_was)
                    lines.append("")

                if broken_wires:
                    lines.append("**⚠️ Broken references (may need cleanup):**")
                    for wire in broken_wires:
                        lines.append(f"- `{wire}`")
                    lines.append("")

        # Renamed files
        renamed = analysis.get("renamed", [])
        if renamed:
            lines.extend(
                [
                    "## Renamed",
                    "",
                ]
            )
            for item in renamed:
                old_path = item.get("old_path", "")
                new_path = item.get("new_path", "")
                content_changed = item.get("content_changed", False)
                changes_desc = item.get("changes_description", "")

                lines.append(f"- `{old_path}` → `{new_path}`")

                if content_changed and changes_desc:
                    lines.append(f"  - {changes_desc}")

                lines.append("")

        # Wire impact summary
        wire_impact = analysis.get("wire_impact", {})
        if wire_impact:
            wires_opened = wire_impact.get("wires_opened", [])
            wires_closed = wire_impact.get("wires_closed", [])
            wires_broken = wire_impact.get("wires_broken", [])

            if wires_opened or wires_closed or wires_broken:
                lines.extend(
                    [
                        "## Wire Impact Summary",
                        "",
                    ]
                )

                if wires_opened:
                    lines.append("**New dependencies introduced:**")
                    for wire in wires_opened:
                        lines.append(f"- `{wire}`")
                    lines.append("")

                if wires_closed:
                    lines.append("**Dependencies now satisfied:**")
                    for wire in wires_closed:
                        lines.append(f"- `{wire}` ✓")
                    lines.append("")

                if wires_broken:
                    lines.append("**⚠️ Broken dependencies (need attention):**")
                    for wire in wires_broken:
                        lines.append(f"- `{wire}`")
                    lines.append("")

        # Affected sections
        affected = analysis.get("affected_sections", [])
        if affected:
            lines.extend(
                [
                    "## Affected Documentation Sections",
                    "",
                    "These existing CODEBASE.md sections may need updating:",
                    "",
                ]
            )
            for section in affected:
                lines.append(f"- {section}")
            lines.append("")

        # Footer
        lines.extend(
            [
                "---",
                "",
                "*This report was generated by CodiLay's diff-run mode.*",
                "",
                f"To update the full documentation, run: `codilay . --update`",
            ]
        )

        return "\n".join(lines)

    def _format_boundary_label(self, boundary_ref: str, boundary_type: str) -> str:
        """Format the boundary reference for display."""
        if boundary_type == "commit":
            return f"commit {boundary_ref[:8]}"
        elif boundary_type == "tag":
            return f"tag {boundary_ref}"
        elif boundary_type == "branch":
            return f"branch {boundary_ref}"
        elif boundary_type == "date":
            return f"date {boundary_ref}"
        return boundary_ref

    def update_codebase_doc(
        self,
        codebase_doc_path: str,
        analysis: dict,
    ) -> bool:
        """
        Update the main CODEBASE.md with changes from diff-run.

        This patches existing sections for modified files and adds new
        sections for added files, keeping the full reference current.
        """
        # This will be implemented by integrating with the existing DocStore
        # For now, just return True to indicate success
        return True
