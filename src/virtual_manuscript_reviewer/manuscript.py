"""Manuscript parsing and handling for PDF documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict
import hashlib

import fitz  # PyMuPDF


@dataclass
class ManuscriptSection:
    """A section of a manuscript."""

    title: str
    content: str
    page_start: int
    page_end: int


@dataclass
class Manuscript:
    """Represents a scientific manuscript extracted from a PDF."""

    title: str
    abstract: str
    full_text: str
    sections: List[ManuscriptSection] = field(default_factory=list)
    source_path: Optional[Path] = None
    version_hash: str = ""
    metadata: Dict = field(default_factory=dict)

    @classmethod
    def from_pdf(cls, pdf_path: Path | str) -> "Manuscript":
        """Extract manuscript content from a PDF file.

        :param pdf_path: Path to the PDF file.
        :return: A Manuscript object with extracted content.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        if not pdf_path.suffix.lower() == ".pdf":
            raise ValueError(f"File is not a PDF: {pdf_path}")

        # Open the PDF
        doc = fitz.open(pdf_path)

        # Extract full text from all pages
        full_text_parts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            full_text_parts.append(text)

        full_text = "\n\n".join(full_text_parts)

        # Try to extract title (usually first large text on first page)
        title = cls._extract_title(doc)

        # Try to extract abstract
        abstract = cls._extract_abstract(full_text)

        # Try to identify sections
        sections = cls._extract_sections(full_text, doc)

        # Extract metadata
        metadata = dict(doc.metadata) if doc.metadata else {}
        metadata["page_count"] = len(doc)

        # Compute version hash for revision tracking
        version_hash = hashlib.sha256(full_text.encode()).hexdigest()[:16]

        doc.close()

        return cls(
            title=title,
            abstract=abstract,
            full_text=full_text,
            sections=sections,
            source_path=pdf_path,
            version_hash=version_hash,
            metadata=metadata,
        )

    @classmethod
    def from_text(cls, text: str, title: str = "Untitled Manuscript") -> "Manuscript":
        """Create a manuscript from raw text.

        :param text: The manuscript text.
        :param title: The manuscript title.
        :return: A Manuscript object.
        """
        abstract = cls._extract_abstract(text)
        version_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        return cls(
            title=title,
            abstract=abstract,
            full_text=text,
            sections=[],
            source_path=None,
            version_hash=version_hash,
            metadata={},
        )

    @staticmethod
    def _extract_title(doc: fitz.Document) -> str:
        """Extract the title from the PDF document.

        :param doc: The PyMuPDF document.
        :return: The extracted title or a default.
        """
        # Try metadata first
        if doc.metadata and doc.metadata.get("title"):
            return doc.metadata["title"]

        # Try to get first line of first page (often the title)
        if len(doc) > 0:
            first_page = doc[0]
            text = first_page.get_text()
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if lines:
                # Title is usually one of the first non-empty lines
                # and is typically short (less than 200 chars)
                for line in lines[:5]:
                    if 10 < len(line) < 200:
                        return line

        return "Untitled Manuscript"

    @staticmethod
    def _extract_abstract(text: str) -> str:
        """Extract the abstract from the manuscript text.

        :param text: The full manuscript text.
        :return: The extracted abstract or empty string.
        """
        text_lower = text.lower()

        # Look for common abstract markers
        abstract_markers = ["abstract", "summary"]
        end_markers = ["introduction", "keywords", "background", "1.", "1 "]

        for marker in abstract_markers:
            start_idx = text_lower.find(marker)
            if start_idx != -1:
                # Find where abstract ends
                search_start = start_idx + len(marker)
                end_idx = len(text)

                for end_marker in end_markers:
                    idx = text_lower.find(end_marker, search_start)
                    if idx != -1 and idx < end_idx:
                        end_idx = idx

                # Extract abstract text
                abstract = text[start_idx:end_idx].strip()

                # Clean up: remove the "Abstract" header itself
                lines = abstract.split("\n")
                if lines and lines[0].lower().strip() in abstract_markers:
                    abstract = "\n".join(lines[1:]).strip()

                # Limit length
                if len(abstract) > 100:  # Minimum reasonable abstract length
                    return abstract[:5000]  # Cap at 5000 chars

        return ""

    @staticmethod
    def _extract_sections(text: str, doc: fitz.Document) -> List[ManuscriptSection]:
        """Extract sections from the manuscript.

        :param text: The full manuscript text.
        :param doc: The PyMuPDF document.
        :return: List of ManuscriptSection objects.
        """
        sections = []

        # Common section headers in biomedical papers
        section_patterns = [
            "abstract",
            "introduction",
            "background",
            "methods",
            "materials and methods",
            "results",
            "discussion",
            "conclusion",
            "conclusions",
            "references",
            "acknowledgements",
            "acknowledgments",
            "supplementary",
            "figures",
            "tables",
        ]

        text_lower = text.lower()
        found_sections = []

        # Find section positions
        for pattern in section_patterns:
            # Look for pattern at start of line or after newline
            search_pos = 0
            while True:
                idx = text_lower.find(pattern, search_pos)
                if idx == -1:
                    break

                # Check if it's at start of line
                if idx == 0 or text[idx - 1] in "\n\r":
                    found_sections.append((idx, pattern.title()))

                search_pos = idx + 1

        # Sort by position
        found_sections.sort(key=lambda x: x[0])

        # Create section objects
        for i, (start_idx, section_title) in enumerate(found_sections):
            end_idx = found_sections[i + 1][0] if i + 1 < len(found_sections) else len(text)
            content = text[start_idx:end_idx].strip()

            # Remove the section header from content
            lines = content.split("\n")
            if lines:
                content = "\n".join(lines[1:]).strip()

            sections.append(ManuscriptSection(
                title=section_title,
                content=content[:10000],  # Cap section length
                page_start=0,  # Would need more complex logic to track pages
                page_end=0,
            ))

        return sections

    def get_review_context(self, max_length: int = 50000) -> str:
        """Get the manuscript content formatted for review.

        :param max_length: Maximum character length to return.
        :return: Formatted manuscript text for review.
        """
        parts = [
            f"# {self.title}",
            "",
            "## Abstract",
            self.abstract if self.abstract else "(No abstract found)",
            "",
            "## Full Text",
            self.full_text[:max_length - len(self.title) - len(self.abstract) - 100],
        ]

        result = "\n".join(parts)

        if len(result) > max_length:
            result = result[:max_length] + "\n\n[Text truncated due to length...]"

        return result

    def __str__(self) -> str:
        """String representation of the manuscript."""
        return f"Manuscript: {self.title} (version: {self.version_hash})"
