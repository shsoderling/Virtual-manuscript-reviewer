"""Revision tracking for manuscript versions and author responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple
import json
import hashlib

from diff_match_patch import diff_match_patch

from virtual_manuscript_reviewer.manuscript import Manuscript
from virtual_manuscript_reviewer.utils import load_review_summary


@dataclass
class RevisionDiff:
    """Represents differences between manuscript versions."""

    additions: list[str] = field(default_factory=list)
    deletions: list[str] = field(default_factory=list)
    changes: list[tuple[str, str]] = field(default_factory=list)
    similarity_score: float = 0.0

    def get_summary(self) -> str:
        """Get a summary of the changes.

        :return: Human-readable summary of changes.
        """
        parts = []

        if self.additions:
            parts.append(f"**Additions ({len(self.additions)}):**")
            for add in self.additions[:5]:  # Limit to first 5
                parts.append(f"  + {add[:200]}...")
            if len(self.additions) > 5:
                parts.append(f"  ... and {len(self.additions) - 5} more additions")

        if self.deletions:
            parts.append(f"\n**Deletions ({len(self.deletions)}):**")
            for deletion in self.deletions[:5]:
                parts.append(f"  - {deletion[:200]}...")
            if len(self.deletions) > 5:
                parts.append(f"  ... and {len(self.deletions) - 5} more deletions")

        parts.append(f"\n**Similarity Score:** {self.similarity_score:.1%}")

        return "\n".join(parts) if parts else "No significant changes detected."


@dataclass
class ManuscriptVersion:
    """Represents a version of a manuscript with its review history."""

    manuscript: Manuscript
    version_number: int
    review_summary: Optional[str] = None
    author_response: Optional[str] = None
    review_path: Optional[Path] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization.

        :return: Dictionary representation.
        """
        return {
            "version_number": self.version_number,
            "version_hash": self.manuscript.version_hash,
            "title": self.manuscript.title,
            "review_summary": self.review_summary,
            "author_response": self.author_response,
            "review_path": str(self.review_path) if self.review_path else None,
            "timestamp": self.timestamp.isoformat(),
            "source_path": str(self.manuscript.source_path) if self.manuscript.source_path else None,
        }


class RevisionTracker:
    """Tracks manuscript revisions and their review history."""

    def __init__(self, project_dir: Path | str = Path("revision_project")):
        """Initialize the revision tracker.

        :param project_dir: Directory to store revision tracking data.
        """
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.versions: list[ManuscriptVersion] = []
        self._dmp = diff_match_patch()

        # Load existing versions if available
        self._load_history()

    def _load_history(self) -> None:
        """Load revision history from disk."""
        history_file = self.project_dir / "revision_history.json"
        if history_file.exists():
            with open(history_file, "r") as f:
                history = json.load(f)

            for version_data in history.get("versions", []):
                # We can't fully reconstruct Manuscript objects without the original files
                # So we just store the metadata for reference
                pass  # Versions are loaded when manuscripts are re-added

    def _save_history(self) -> None:
        """Save revision history to disk."""
        history_file = self.project_dir / "revision_history.json"
        history = {
            "versions": [v.to_dict() for v in self.versions],
            "last_updated": datetime.now().isoformat(),
        }
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)

    def add_version(
        self,
        manuscript: Manuscript,
        author_response: Optional[str] = None,
    ) -> ManuscriptVersion:
        """Add a new manuscript version to track.

        :param manuscript: The manuscript to add.
        :param author_response: The authors' response to previous reviews.
        :return: The created ManuscriptVersion.
        """
        version_number = len(self.versions) + 1

        version = ManuscriptVersion(
            manuscript=manuscript,
            version_number=version_number,
            author_response=author_response,
        )

        self.versions.append(version)
        self._save_history()

        return version

    def add_review(
        self,
        version_number: int,
        review_summary: str,
        review_path: Optional[Path] = None,
    ) -> None:
        """Add a review to a manuscript version.

        :param version_number: The version number.
        :param review_summary: The review summary text.
        :param review_path: Path to the full review file.
        """
        if version_number < 1 or version_number > len(self.versions):
            raise ValueError(f"Invalid version number: {version_number}")

        version = self.versions[version_number - 1]
        version.review_summary = review_summary
        version.review_path = review_path

        self._save_history()

    def compare_versions(
        self,
        version_a: int,
        version_b: int,
    ) -> RevisionDiff:
        """Compare two manuscript versions.

        :param version_a: First version number.
        :param version_b: Second version number.
        :return: RevisionDiff showing changes.
        """
        if version_a < 1 or version_a > len(self.versions):
            raise ValueError(f"Invalid version number: {version_a}")
        if version_b < 1 or version_b > len(self.versions):
            raise ValueError(f"Invalid version number: {version_b}")

        text_a = self.versions[version_a - 1].manuscript.full_text
        text_b = self.versions[version_b - 1].manuscript.full_text

        # Compute diff
        diffs = self._dmp.diff_main(text_a, text_b)
        self._dmp.diff_cleanupSemantic(diffs)

        additions = []
        deletions = []
        changes = []

        for op, text in diffs:
            if op == 1:  # Addition
                additions.append(text.strip())
            elif op == -1:  # Deletion
                deletions.append(text.strip())

        # Calculate similarity score using Levenshtein distance
        levenshtein = self._dmp.diff_levenshtein(diffs)
        max_len = max(len(text_a), len(text_b))
        similarity = 1.0 - (levenshtein / max_len) if max_len > 0 else 1.0

        return RevisionDiff(
            additions=[a for a in additions if len(a) > 20],  # Filter trivial changes
            deletions=[d for d in deletions if len(d) > 20],
            changes=changes,
            similarity_score=similarity,
        )

    def get_previous_reviews(self) -> tuple[str, ...]:
        """Get all previous review summaries.

        :return: Tuple of review summaries.
        """
        reviews = []
        for version in self.versions:
            if version.review_summary:
                reviews.append(version.review_summary)
        return tuple(reviews)

    def get_latest_version(self) -> Optional[ManuscriptVersion]:
        """Get the most recent manuscript version.

        :return: The latest ManuscriptVersion or None.
        """
        return self.versions[-1] if self.versions else None

    def get_revision_context(self) -> str:
        """Get context about the revision history for reviewers.

        :return: Formatted revision context.
        """
        if len(self.versions) <= 1:
            return ""

        parts = [f"This manuscript is on revision {len(self.versions)}."]

        for i, version in enumerate(self.versions[:-1], 1):
            if version.review_summary:
                parts.append(f"\n### Version {i} Review Summary")
                parts.append(version.review_summary[:2000])  # Limit length

            if version.author_response:
                parts.append(f"\n### Authors' Response to Version {i} Review")
                parts.append(version.author_response[:2000])

        # Show diff from previous version
        if len(self.versions) >= 2:
            diff = self.compare_versions(len(self.versions) - 1, len(self.versions))
            parts.append("\n### Changes from Previous Version")
            parts.append(diff.get_summary())

        return "\n\n".join(parts)

    def generate_revision_report(self) -> str:
        """Generate a comprehensive revision history report.

        :return: Markdown-formatted report.
        """
        lines = ["# Manuscript Revision History", ""]

        for i, version in enumerate(self.versions, 1):
            lines.append(f"## Version {i}")
            lines.append(f"- **Title:** {version.manuscript.title}")
            lines.append(f"- **Hash:** {version.manuscript.version_hash}")
            lines.append(f"- **Timestamp:** {version.timestamp.strftime('%Y-%m-%d %H:%M')}")

            if version.review_summary:
                lines.append(f"\n### Review Summary")
                lines.append(version.review_summary[:1000] + "..." if len(version.review_summary) > 1000 else version.review_summary)

            if version.author_response:
                lines.append(f"\n### Author Response")
                lines.append(version.author_response[:1000] + "..." if len(version.author_response) > 1000 else version.author_response)

            # Show changes from previous version
            if i > 1:
                diff = self.compare_versions(i - 1, i)
                lines.append(f"\n### Changes from Version {i-1}")
                lines.append(diff.get_summary())

            lines.append("")

        return "\n".join(lines)

    def save_report(self, filename: str = "revision_report.md") -> Path:
        """Save the revision report to a file.

        :param filename: Name of the report file.
        :return: Path to the saved report.
        """
        report = self.generate_revision_report()
        report_path = self.project_dir / filename

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        return report_path
