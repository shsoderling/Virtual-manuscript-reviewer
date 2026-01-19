"""PDF generation for manuscript reviews and mentor reports."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    ListFlowable,
    ListItem,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY


def _create_styles() -> dict:
    """Create custom paragraph styles for PDF generation.

    :return: Dictionary of paragraph styles.
    """
    styles = getSampleStyleSheet()

    # Helper function to safely add styles (avoid duplicates)
    def add_style(name: str, **kwargs):
        if name not in styles.byName:
            styles.add(ParagraphStyle(name=name, **kwargs))

    # Title style
    add_style(
        'DocTitle',
        parent=styles['Title'],
        fontSize=18,
        spaceAfter=20,
        textColor=colors.HexColor('#1a365d'),
        alignment=TA_CENTER,
    )

    # Subtitle style
    add_style(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=30,
        textColor=colors.HexColor('#4a5568'),
        alignment=TA_CENTER,
    )

    # Section header style (H2)
    add_style(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor('#2c5282'),
        borderPadding=(0, 0, 4, 0),
    )

    # Subsection header style (H3)
    add_style(
        'SubsectionHeader',
        parent=styles['Heading3'],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor('#2b6cb0'),
    )

    # Sub-subsection header style (H4)
    add_style(
        'SubSubsectionHeader',
        parent=styles['Heading4'],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor('#3182ce'),
        fontName='Helvetica-BoldOblique',
    )

    # Body text style - use a different name to avoid conflict with built-in
    add_style(
        'ReviewBodyText',
        parent=styles['Normal'],
        fontSize=10,
        spaceBefore=4,
        spaceAfter=4,
        alignment=TA_JUSTIFY,
        leading=14,
    )

    # Bullet point style
    add_style(
        'BulletText',
        parent=styles['Normal'],
        fontSize=10,
        spaceBefore=2,
        spaceAfter=2,
        leftIndent=20,
        leading=14,
    )

    # Numbered list style
    add_style(
        'NumberedText',
        parent=styles['Normal'],
        fontSize=10,
        spaceBefore=2,
        spaceAfter=2,
        leftIndent=20,
        leading=14,
    )

    # Recommendation box style
    add_style(
        'Recommendation',
        parent=styles['Normal'],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=12,
        textColor=colors.HexColor('#1a365d'),
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        borderPadding=10,
    )

    # Mentor advice style
    add_style(
        'MentorAdvice',
        parent=styles['Normal'],
        fontSize=10,
        spaceBefore=6,
        spaceAfter=6,
        leftIndent=10,
        rightIndent=10,
        backColor=colors.HexColor('#f7fafc'),
        borderPadding=8,
        leading=14,
    )

    return styles


def _markdown_to_flowables(text: str, styles: dict) -> list:
    """Convert markdown-like text to ReportLab flowables.

    :param text: The markdown text.
    :param styles: The paragraph styles.
    :return: List of flowables.
    """
    flowables = []
    lines = text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if not line:
            flowables.append(Spacer(1, 6))
            i += 1
            continue

        # Headers
        if line.startswith('#### '):
            flowables.append(Paragraph(line[5:], styles['SubSubsectionHeader']))
        elif line.startswith('### '):
            flowables.append(Paragraph(line[4:], styles['SubsectionHeader']))
        elif line.startswith('## '):
            flowables.append(Paragraph(line[3:], styles['SectionHeader']))
        elif line.startswith('# '):
            flowables.append(Paragraph(line[2:], styles['DocTitle']))
        # Numbered list items
        elif re.match(r'^\d+\.\s', line):
            # Extract the text after the number
            match = re.match(r'^(\d+)\.\s(.+)$', line)
            if match:
                num, content = match.groups()
                content = _escape_html(content)
                content = _apply_inline_formatting(content)
                flowables.append(Paragraph(f"{num}. {content}", styles['NumberedText']))
        # Bullet points
        elif line.startswith('- ') or line.startswith('* '):
            content = line[2:]
            content = _escape_html(content)
            content = _apply_inline_formatting(content)
            flowables.append(Paragraph(f"• {content}", styles['BulletText']))
        # Regular paragraph
        else:
            content = _escape_html(line)
            content = _apply_inline_formatting(content)
            flowables.append(Paragraph(content, styles['ReviewBodyText']))

        i += 1

    return flowables


def _escape_html(text: str) -> str:
    """Escape HTML special characters.

    :param text: The text to escape.
    :return: Escaped text.
    """
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def _apply_inline_formatting(text: str) -> str:
    """Apply inline markdown formatting (bold, italic).

    :param text: The text with markdown formatting.
    :return: Text with ReportLab formatting tags.
    """
    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)

    # Italic: *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)

    # Code: `text`
    text = re.sub(r'`(.+?)`', r'<font face="Courier">\1</font>', text)

    return text


def generate_review_pdf(
    discussion: list[dict[str, str]],
    manuscript_title: str,
    output_path: Path,
    include_full_discussion: bool = False,
) -> Path:
    """Generate a PDF of the review.

    :param discussion: The review discussion.
    :param manuscript_title: The title of the manuscript.
    :param output_path: Where to save the PDF.
    :param include_full_discussion: Whether to include full discussion or just summary.
    :return: Path to the generated PDF.
    """
    styles = _create_styles()

    # Create PDF document
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
    )

    flowables = []

    # Title page
    flowables.append(Paragraph("Manuscript Review", styles['DocTitle']))
    flowables.append(Spacer(1, 10))

    # Manuscript title (truncate if too long)
    display_title = manuscript_title[:100] + "..." if len(manuscript_title) > 100 else manuscript_title
    flowables.append(Paragraph(f"<i>{display_title}</i>", styles['DocSubtitle']))

    # Date
    date_str = datetime.now().strftime("%B %d, %Y")
    flowables.append(Paragraph(f"Generated: {date_str}", styles['DocSubtitle']))
    flowables.append(Spacer(1, 20))

    # Get the final summary (last message from Editor)
    final_summary = None
    for turn in reversed(discussion):
        if turn['agent'] == 'Editor':
            final_summary = turn['message']
            break

    if final_summary:
        # Convert markdown to flowables
        flowables.extend(_markdown_to_flowables(final_summary, styles))

    # Optionally include full discussion
    if include_full_discussion:
        flowables.append(PageBreak())
        flowables.append(Paragraph("Full Review Discussion", styles['DocTitle']))
        flowables.append(Spacer(1, 20))

        for turn in discussion:
            if turn['agent'] == 'User':
                continue  # Skip user prompts

            flowables.append(Paragraph(f"<b>{turn['agent']}</b>", styles['SectionHeader']))
            flowables.extend(_markdown_to_flowables(turn['message'], styles))
            flowables.append(Spacer(1, 12))

    # Build PDF
    doc.build(flowables)

    return output_path


def generate_mentor_pdf(
    mentor_report: str,
    manuscript_title: str,
    output_path: Path,
) -> Path:
    """Generate a PDF of the scientific mentor report.

    :param mentor_report: The mentor's advice and recommendations.
    :param manuscript_title: The title of the manuscript.
    :param output_path: Where to save the PDF.
    :return: Path to the generated PDF.
    """
    styles = _create_styles()

    # Create PDF document
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
    )

    flowables = []

    # Title page
    flowables.append(Paragraph("Scientific Mentor Report", styles['DocTitle']))
    flowables.append(Spacer(1, 10))
    flowables.append(Paragraph("Guidance for Addressing Reviewer Concerns", styles['DocSubtitle']))
    flowables.append(Spacer(1, 10))

    # Manuscript title
    display_title = manuscript_title[:100] + "..." if len(manuscript_title) > 100 else manuscript_title
    flowables.append(Paragraph(f"<i>{display_title}</i>", styles['DocSubtitle']))

    # Date
    date_str = datetime.now().strftime("%B %d, %Y")
    flowables.append(Paragraph(f"Generated: {date_str}", styles['DocSubtitle']))
    flowables.append(Spacer(1, 30))

    # Convert mentor report markdown to flowables
    flowables.extend(_markdown_to_flowables(mentor_report, styles))

    # Build PDF
    doc.build(flowables)

    return output_path
