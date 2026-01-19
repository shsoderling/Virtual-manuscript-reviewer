# Virtual Manuscript Reviewer

An AI-powered manuscript review system using multi-agent LLM collaboration for biomedical research papers. Forked from [Virtual Lab](https://github.com/zou-group/virtual-lab).

## Overview

Virtual Manuscript Reviewer uses multiple AI agents with specialized expertise to provide comprehensive peer review feedback for scientific manuscripts. The system simulates a traditional peer review process with:

- **Editor**: Synthesizes feedback and provides overall recommendations
- **Methodology Reviewer**: Evaluates experimental design, statistics, and reproducibility
- **Domain Expert**: Assesses scientific accuracy, novelty, and significance
- **Presentation Reviewer**: Reviews clarity, writing quality, and figure effectiveness

## Features

- **PDF Manuscript Input**: Automatically extracts text from PDF manuscripts
- **Multi-Agent Review Panel**: Multiple specialized reviewers provide comprehensive feedback
- **Structured Output**: Reviews follow standard peer review format (Summary, Strengths, Weaknesses, Specific Comments, Recommendation)
- **Revision Tracking**: Track manuscript versions and compare changes between revisions
- **PubMed Integration**: Reviewers can search PubMed to verify claims and check related literature
- **Configurable Review Criteria**: Customize evaluation criteria for different manuscript types

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/virtual-manuscript-reviewer.git
cd virtual-manuscript-reviewer

# Install with pip
pip install -e .

# Or install dependencies manually
pip install openai requests tiktoken tqdm typed-argument-parser pymupdf diff-match-patch
```

## Configuration

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Usage

### Command Line

```bash
# Basic review of a manuscript
vmr --pdf manuscript.pdf

# Review with multiple discussion rounds
vmr --pdf manuscript.pdf --num-rounds 2

# Review with revision tracking
vmr --pdf revised_manuscript.pdf --project-dir my_project --author-response response.txt

# Individual review (single reviewer with critic feedback)
vmr --pdf manuscript.pdf --review-type individual
```

### Python API

```python
from virtual_manuscript_reviewer import Manuscript, run_review
from virtual_manuscript_reviewer.prompts import BIOMEDICAL_REVIEW_CRITERIA

# Load manuscript from PDF
manuscript = Manuscript.from_pdf("path/to/manuscript.pdf")

# Run panel review
summary = run_review(
    manuscript=manuscript,
    review_type="panel",
    save_dir="reviews",
    review_criteria=BIOMEDICAL_REVIEW_CRITERIA,
    num_rounds=1,
    return_summary=True,
)

print(summary)
```

### Revision Tracking

```python
from virtual_manuscript_reviewer import Manuscript
from virtual_manuscript_reviewer.revision_tracker import RevisionTracker

# Initialize tracker
tracker = RevisionTracker("my_project")

# Add initial version
manuscript_v1 = Manuscript.from_pdf("manuscript_v1.pdf")
version = tracker.add_version(manuscript_v1)

# After review, add the review
tracker.add_review(
    version_number=1,
    review_summary="...",
    review_path=Path("reviews/review_v1.json"),
)

# Add revised version with author response
manuscript_v2 = Manuscript.from_pdf("manuscript_v2.pdf")
tracker.add_version(
    manuscript_v2,
    author_response="We thank the reviewers for their feedback..."
)

# Compare versions
diff = tracker.compare_versions(1, 2)
print(diff.get_summary())

# Generate revision report
report_path = tracker.save_report()
```

## Output Format

Reviews are saved in both JSON and Markdown formats:

```
reviews/
├── Manuscript_Title_abc123.json    # Full discussion transcript
└── Manuscript_Title_abc123.md      # Formatted review summary
```

### Review Structure

```markdown
### Summary
Brief summary of the manuscript's main findings and contributions.

### Major Strengths
- Key strength 1
- Key strength 2

### Major Weaknesses
- Significant weakness that must be addressed
- Another major concern

### Minor Issues
- Minor suggestion for improvement
- Typo on page X

### Specific Comments
Detailed, section-by-section feedback.

### Recommendation
Accept / Minor Revisions / Major Revisions / Reject
Justification for the recommendation.
```

## Customizing Reviewers

```python
from virtual_manuscript_reviewer.agent import Agent
from virtual_manuscript_reviewer.run_review import run_review

# Create custom reviewer
statistics_reviewer = Agent(
    title="Statistics Reviewer",
    expertise="biostatistics, clinical trial design, and statistical methodology",
    goal="ensure all statistical analyses are appropriate and correctly interpreted",
    role="evaluate the statistical methods, sample sizes, and interpretation of results",
    model="gpt-4o",
)

# Use in review
run_review(
    manuscript=manuscript,
    review_type="panel",
    reviewers=(statistics_reviewer,),  # Custom reviewer panel
)
```

## Review Criteria

Default biomedical review criteria include:

1. Scientific rigor
2. Novelty
3. Significance
4. Data quality
5. Reproducibility
6. Claims vs. evidence
7. Presentation
8. Figures and tables
9. Ethics

Customize by passing your own criteria:

```python
custom_criteria = (
    "Is the research question clearly stated?",
    "Are the methods appropriate for the research question?",
    "Are the conclusions supported by the data?",
)

run_review(manuscript=manuscript, review_criteria=custom_criteria)
```

## Cost Estimation

The system tracks token usage and provides cost estimates after each review:

```
Input token count: 45,000
Output token count: 8,000
Tool token count: 2,000
Max token length: 55,000
Cost: $1.25
Time: 3:45
```

## Limitations

- Reviews are AI-generated and should be used as a supplement to, not replacement for, human peer review
- PDF parsing may not perfectly extract all content from complex layouts
- Large manuscripts may be truncated to fit context limits
- The system works best with English-language manuscripts

## License

MIT License

## Acknowledgments

Based on the [Virtual Lab](https://github.com/zou-group/virtual-lab) framework by Swanson et al. (Nature, 2025).
