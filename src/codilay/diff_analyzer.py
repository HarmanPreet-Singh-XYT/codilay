"""
Diff analyzer — extracts and analyzes code changes since a boundary commit/date/branch.

This module provides focused diff extraction for the diff-run feature, which documents
only what changed after a specific boundary rather than the entire codebase.
"""

import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from codilay.git_tracker import ChangeType, FileChange


@dataclass
class FileDiff:
    """Represents the diff content for a single file."""

    path: str
    change_type: ChangeType
    old_path: Optional[str] = None
    diff_content: Optional[str] = None  # The actual diff (patch format)
    full_content: Optional[str] = None  # Full file content (for new files)


@dataclass
class DiffAnalysisResult:
    """Complete result of a diff-run analysis."""

    boundary_ref: str  # The commit/tag/branch used as boundary
    boundary_type: str  # 'commit', 'tag', 'branch', 'date'
    head_commit: str
    commits_count: int
    commit_messages: List[str] = field(default_factory=list)
    file_diffs: List[FileDiff] = field(default_factory=list)

    @property
    def added_files(self) -> List[FileDiff]:
        return [f for f in self.file_diffs if f.change_type == ChangeType.ADDED]

    @property
    def modified_files(self) -> List[FileDiff]:
        return [f for f in self.file_diffs if f.change_type == ChangeType.MODIFIED]

    @property
    def deleted_files(self) -> List[FileDiff]:
        return [f for f in self.file_diffs if f.change_type == ChangeType.DELETED]

    @property
    def renamed_files(self) -> List[FileDiff]:
        return [f for f in self.file_diffs if f.change_type == ChangeType.RENAMED]


class DiffAnalyzer:
    """
    Analyzes code changes between a boundary and HEAD for diff-run mode.

    Unlike full codebase scans, this extracts only the diffs (what changed)
    rather than full file contents, making it far more token-efficient.
    """

    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        self._validate_repo()

    def _validate_repo(self):
        """Check if the target path is a git repository."""
        self._is_git_repo = os.path.isdir(os.path.join(self.repo_path, ".git"))

    @property
    def is_git_repo(self) -> bool:
        return self._is_git_repo

    def _run_git(self, *args, check: bool = True) -> Optional[str]:
        """Run a git command and return stdout."""
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if check and result.returncode != 0:
                return None
            return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def resolve_boundary(
        self, since: Optional[str] = None, since_branch: Optional[str] = None
    ) -> Optional[Tuple[str, str]]:
        """
        Resolve the boundary reference to a commit hash.

        Returns (commit_hash, boundary_type) or None if invalid.

        Supports:
        - Commit hash: abc123f
        - Tag: v2.1.0
        - Date: 2024-03-01 (finds first commit after this date)
        - Branch: feature-branch (via --since-branch)
        """
        if since_branch:
            # Find merge base between current branch and target branch
            merge_base = self._run_git("merge-base", "HEAD", since_branch)
            if merge_base:
                return (merge_base, "branch")
            return None

        if not since:
            return None

        # Try as commit hash first
        result = self._run_git("cat-file", "-t", since, check=False)
        if result == "commit":
            return (since, "commit")

        # Try as tag
        tag_commit = self._run_git("rev-list", "-n", "1", since, check=False)
        if tag_commit:
            return (tag_commit, "tag")

        # Try as date (find first commit after this date)
        try:
            # Validate date format
            datetime.strptime(since, "%Y-%m-%d")
            commit = self._run_git("rev-list", "-1", f"--before={since}", "HEAD")
            if commit:
                return (commit, "date")
        except ValueError:
            pass

        return None

    def analyze(self, since: Optional[str] = None, since_branch: Optional[str] = None) -> Optional[DiffAnalysisResult]:
        """
        Analyze changes since the boundary.

        Returns a DiffAnalysisResult with:
        - List of changed files with their diffs
        - Commit messages in the range
        - Full content for newly added files
        - Patch diffs for modified files
        """
        if not self.is_git_repo:
            return None

        boundary = self.resolve_boundary(since=since, since_branch=since_branch)
        if not boundary:
            return None

        base_commit, boundary_type = boundary

        head_commit = self._run_git("rev-parse", "HEAD")
        if not head_commit:
            return None

        # Get commit count and messages
        commits_count_str = self._run_git("rev-list", "--count", f"{base_commit}..HEAD")
        commits_count = int(commits_count_str) if commits_count_str else 0

        commit_messages_output = self._run_git("log", "--oneline", "--no-decorate", f"{base_commit}..HEAD")
        commit_messages = commit_messages_output.strip().split("\n") if commit_messages_output else []

        # Get changed files (name-status)
        name_status_output = self._run_git("diff", "--name-status", "-M", "-C", base_commit, "HEAD")
        if not name_status_output:
            # No changes
            return DiffAnalysisResult(
                boundary_ref=since or since_branch or base_commit,
                boundary_type=boundary_type,
                head_commit=head_commit,
                commits_count=commits_count,
                commit_messages=commit_messages,
                file_diffs=[],
            )

        file_changes = self._parse_name_status(name_status_output)

        # For each file, extract the appropriate content
        file_diffs = []
        for change in file_changes:
            if change.change_type == ChangeType.ADDED:
                # New file — get full content
                full_content = self._read_file(change.path)
                file_diffs.append(
                    FileDiff(
                        path=change.path,
                        change_type=ChangeType.ADDED,
                        full_content=full_content,
                    )
                )

            elif change.change_type == ChangeType.MODIFIED:
                # Modified file — get diff patch
                diff_content = self._get_file_diff(base_commit, change.path)
                file_diffs.append(
                    FileDiff(
                        path=change.path,
                        change_type=ChangeType.MODIFIED,
                        diff_content=diff_content,
                    )
                )

            elif change.change_type == ChangeType.DELETED:
                # Deleted file — no content needed, just the record
                file_diffs.append(
                    FileDiff(
                        path=change.path,
                        change_type=ChangeType.DELETED,
                    )
                )

            elif change.change_type == ChangeType.RENAMED:
                # Renamed file — get diff of content changes (if any)
                diff_content = self._get_file_diff(base_commit, change.path)
                file_diffs.append(
                    FileDiff(
                        path=change.path,
                        change_type=ChangeType.RENAMED,
                        old_path=change.old_path,
                        diff_content=diff_content,
                    )
                )

        return DiffAnalysisResult(
            boundary_ref=since or since_branch or base_commit,
            boundary_type=boundary_type,
            head_commit=head_commit,
            commits_count=commits_count,
            commit_messages=commit_messages,
            file_diffs=file_diffs,
        )

    def _parse_name_status(self, output: str) -> List[FileChange]:
        """Parse git diff --name-status output."""
        changes = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            parts = line.split("\t")
            if len(parts) < 2:
                continue

            status = parts[0].strip()

            if status == "A":
                changes.append(FileChange(change_type=ChangeType.ADDED, path=parts[1]))

            elif status == "M":
                changes.append(FileChange(change_type=ChangeType.MODIFIED, path=parts[1]))

            elif status == "D":
                changes.append(FileChange(change_type=ChangeType.DELETED, path=parts[1]))

            elif status.startswith("R"):
                # Rename
                if len(parts) >= 3:
                    similarity = None
                    if len(status) > 1:
                        try:
                            similarity = int(status[1:])
                        except ValueError:
                            pass

                    changes.append(
                        FileChange(
                            change_type=ChangeType.RENAMED,
                            path=parts[2],
                            old_path=parts[1],
                            similarity=similarity,
                        )
                    )

            elif status.startswith("C"):
                # Copy
                if len(parts) >= 3:
                    changes.append(
                        FileChange(
                            change_type=ChangeType.COPIED,
                            path=parts[2],
                            old_path=parts[1],
                        )
                    )

        return changes

    def _get_file_diff(self, base_commit: str, filepath: str) -> Optional[str]:
        """Get the unified diff for a specific file."""
        diff = self._run_git("diff", base_commit, "HEAD", "--", filepath, check=False)
        return diff if diff else None

    def _read_file(self, filepath: str) -> Optional[str]:
        """Read the current content of a file."""
        full_path = os.path.join(self.repo_path, filepath)
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except (FileNotFoundError, PermissionError):
            return None

    def get_existing_doc_sections(self, docstore, modified_paths: List[str]) -> Dict[str, str]:
        """
        Get existing CODEBASE.md sections for modified files.

        This provides context to the LLM about what was documented before,
        so it can describe changes relative to the existing understanding.
        """
        sections = {}
        for path in modified_paths:
            section = docstore.get_section_by_path(path)
            if section:
                sections[path] = section
        return sections
