"""Prompts and pre-configured reviewer agents for manuscript review."""

from typing import Iterable

from virtual_manuscript_reviewer.agent import Agent
from virtual_manuscript_reviewer.constants import DEFAULT_MODEL


# =============================================================================
# Pre-configured Reviewer Agents
# =============================================================================

EDITOR = Agent(
    title="Editor",
    expertise="scientific publishing, editorial decision-making, and manuscript evaluation for biomedical journals",
    goal="provide a fair and thorough assessment of the manuscript's suitability for publication, considering novelty, significance, and scientific rigor",
    role="synthesize feedback from specialist reviewers, identify the most critical issues, and provide an overall recommendation on the manuscript",
    model=DEFAULT_MODEL,
)

METHODOLOGY_REVIEWER = Agent(
    title="Methodology Reviewer",
    expertise="experimental design, statistical analysis, and methodological rigor in biomedical research",
    goal="ensure the methods are sound, reproducible, and appropriate for the research questions",
    role="critically evaluate the experimental design, statistical approaches, sample sizes, controls, and reproducibility of the methods. Identify any methodological flaws or areas needing clarification",
    model=DEFAULT_MODEL,
)

DOMAIN_EXPERT = Agent(
    title="Domain Expert",
    expertise="biomedical sciences, current literature, and the specific research area of the manuscript",
    goal="assess the scientific accuracy, novelty, and significance of the research in the context of the field",
    role="evaluate whether the findings are novel, scientifically sound, and significant. Assess how well the manuscript relates to existing literature and whether claims are supported by the data",
    model=DEFAULT_MODEL,
)

PRESENTATION_REVIEWER = Agent(
    title="Presentation Reviewer",
    expertise="scientific writing, data visualization, and clear communication of research findings",
    goal="ensure the manuscript is clearly written, well-organized, and effectively communicates its findings",
    role="evaluate the clarity of writing, quality of figures and tables, logical organization, and overall readability. Identify areas where presentation could be improved",
    model=DEFAULT_MODEL,
)

SCIENTIFIC_CRITIC = Agent(
    title="Scientific Critic",
    expertise="providing rigorous critical feedback for scientific manuscripts",
    goal="ensure that reviews are thorough, fair, and constructively critical",
    role="provide critical feedback on the review process to ensure all important issues are identified and feedback is actionable",
    model=DEFAULT_MODEL,
)


# Default review panel
DEFAULT_REVIEWERS = (METHODOLOGY_REVIEWER, DOMAIN_EXPERT, PRESENTATION_REVIEWER)


# =============================================================================
# Prompt Formatting Functions
# =============================================================================

SYNTHESIS_PROMPT = "synthesize the points raised by each reviewer, identify the most critical issues, and determine the overall assessment of the manuscript"

SUMMARY_PROMPT = "summarize the review discussion, provide specific recommendations for the authors, and give a final publication recommendation"


def format_prompt_list(prompts: Iterable[str]) -> str:
    """Formats prompts as a numbered list.

    :param prompts: The prompts.
    :return: The prompts formatted as a numbered list.
    """
    return "\n\n".join(f"{i + 1}. {prompt}" for i, prompt in enumerate(prompts))


def format_manuscript(manuscript_text: str, intro: str = "Here is the manuscript to review:") -> str:
    """Formats the manuscript for the prompt.

    :param manuscript_text: The manuscript content.
    :param intro: The introduction to the manuscript.
    :return: The formatted manuscript.
    """
    return f"{intro}\n\n[begin manuscript]\n\n{manuscript_text}\n\n[end manuscript]\n\n"


def format_review_criteria(
    criteria: tuple[str, ...],
    intro: str = "Please evaluate the manuscript on the following criteria:",
) -> str:
    """Formats the review criteria for the prompt.

    :param criteria: The review criteria.
    :param intro: The introduction to the criteria.
    :return: The formatted criteria.
    """
    return f"{intro}\n\n{format_prompt_list(criteria)}\n\n" if criteria else ""


def format_previous_reviews(
    reviews: tuple[str, ...],
    intro: str = "Here are the previous reviews of this manuscript:",
) -> str:
    """Formats previous reviews for revision tracking.

    :param reviews: Previous review summaries.
    :param intro: The introduction to the reviews.
    :return: The formatted reviews.
    """
    if not reviews:
        return ""

    formatted = [
        f"[begin review {i + 1}]\n\n{review}\n\n[end review {i + 1}]"
        for i, review in enumerate(reviews)
    ]
    return f"{intro}\n\n{''.join(formatted)}\n\n"


def format_author_response(
    response: str,
    intro: str = "Here is the authors' response to previous reviews:",
) -> str:
    """Formats the authors' response to previous reviews.

    :param response: The author response text.
    :param intro: The introduction.
    :return: The formatted response.
    """
    if not response:
        return ""
    return f"{intro}\n\n[begin author response]\n\n{response}\n\n[end author response]\n\n"


def review_structure_prompt() -> str:
    """Returns the expected structure for the review summary.

    :return: The review structure prompt.
    """
    return """Your review should follow this structure:

### Summary
Provide a brief summary of the manuscript's main findings and contributions.

### Major Strengths
List the key strengths of the manuscript (2-4 points).

### Major Weaknesses
List the significant weaknesses that must be addressed (2-4 points).

### Minor Issues
List minor issues or suggestions for improvement.

### Conclusions Assessment
Evaluate each major conclusion of the manuscript:

#### Conclusions Supported by the Data
List conclusions that ARE adequately supported by the presented evidence. For each, briefly explain what data supports it.

#### Conclusions NOT Supported by the Data
List conclusions that are NOT adequately supported, overstated, or require additional evidence. For each:
- State the claim made by the authors
- Explain why the current data is insufficient
- Specify what additional data or analysis would be needed

### Specific Comments
Provide detailed, line-by-line or section-by-section feedback.

### Recommendation
Provide one of: Accept, Minor Revisions, Major Revisions, or Reject.
Justify your recommendation based on the above assessment."""


# =============================================================================
# Review Meeting Prompts
# =============================================================================

def review_meeting_start_prompt(
    editor: Agent,
    reviewers: tuple[Agent, ...],
    manuscript_text: str,
    review_criteria: tuple[str, ...] = (),
    previous_reviews: tuple[str, ...] = (),
    author_response: str = "",
    num_rounds: int = 1,
) -> str:
    """Generates the start prompt for a review meeting.

    :param editor: The editor leading the review.
    :param reviewers: The reviewer panel.
    :param manuscript_text: The manuscript content.
    :param review_criteria: Specific criteria to evaluate.
    :param previous_reviews: Previous reviews (for revision tracking).
    :param author_response: Authors' response to previous reviews.
    :param num_rounds: Number of discussion rounds.
    :return: The start prompt.
    """
    is_revision = len(previous_reviews) > 0

    revision_context = ""
    if is_revision:
        revision_context = (
            "This is a REVISED manuscript. Please evaluate how well the authors have addressed previous concerns.\n\n"
            f"{format_previous_reviews(previous_reviews)}"
            f"{format_author_response(author_response)}"
        )

    return (
        f"This is a manuscript review meeting to evaluate a scientific paper for publication. "
        f"The review panel consists of the {editor.title} and the following reviewers: "
        f"{', '.join(reviewer.title for reviewer in reviewers)}.\n\n"
        f"{revision_context}"
        f"{format_manuscript(manuscript_text)}"
        f"{format_review_criteria(review_criteria)}"
        f"The {editor.title} will convene the meeting and provide initial impressions. "
        f"Then, each reviewer will provide their assessment one-by-one. "
        f"After all reviewers have given their input, the {editor.title} will {SYNTHESIS_PROMPT}. "
        f"This will continue for {num_rounds} round(s). "
        f"Finally, the {editor.title} will {SUMMARY_PROMPT}."
    )


def review_meeting_editor_initial_prompt(editor: Agent) -> str:
    """Generates the initial prompt for the editor.

    :param editor: The editor.
    :return: The initial prompt.
    """
    return (
        f"{editor}, please provide your initial impressions of the manuscript "
        f"and highlight the key areas you would like the reviewers to focus on."
    )


def review_meeting_reviewer_prompt(reviewer: Agent, round_num: int, num_rounds: int) -> str:
    """Generates the prompt for a reviewer.

    :param reviewer: The reviewer.
    :param round_num: The current round number.
    :param num_rounds: The total number of rounds.
    :return: The reviewer prompt.
    """
    return (
        f"{reviewer}, please provide your assessment of the manuscript (round {round_num} of {num_rounds}). "
        f"Focus on your area of expertise. "
        f'If you do not have anything new or relevant to add, you may say "pass". '
        f"You may respectfully disagree with other reviewers if you have a different perspective."
    )


def review_meeting_editor_intermediate_prompt(editor: Agent, round_num: int, num_rounds: int) -> str:
    """Generates the intermediate prompt for the editor.

    :param editor: The editor.
    :param round_num: The current round number.
    :param num_rounds: The total number of rounds.
    :return: The intermediate prompt.
    """
    return (
        f"This concludes round {round_num} of {num_rounds} of the review discussion. "
        f"{editor}, please {SYNTHESIS_PROMPT}."
    )


def review_meeting_editor_final_prompt(
    editor: Agent,
    review_criteria: tuple[str, ...] = (),
) -> str:
    """Generates the final prompt for the editor to summarize.

    :param editor: The editor.
    :param review_criteria: The review criteria.
    :return: The final prompt.
    """
    criteria_reminder = ""
    if review_criteria:
        criteria_reminder = format_review_criteria(
            review_criteria,
            intro="As a reminder, here are the review criteria that must be addressed:"
        )

    return (
        f"{editor}, please {SUMMARY_PROMPT}.\n\n"
        f"{criteria_reminder}"
        f"Your summary should take the following form:\n\n"
        f"{review_structure_prompt()}"
    )


# =============================================================================
# Individual Review Prompts (Single reviewer with critic feedback)
# =============================================================================

def individual_review_start_prompt(
    reviewer: Agent,
    manuscript_text: str,
    review_criteria: tuple[str, ...] = (),
    previous_reviews: tuple[str, ...] = (),
    author_response: str = "",
) -> str:
    """Generates the start prompt for an individual review.

    :param reviewer: The reviewer.
    :param manuscript_text: The manuscript content.
    :param review_criteria: Specific criteria to evaluate.
    :param previous_reviews: Previous reviews (for revision tracking).
    :param author_response: Authors' response to previous reviews.
    :return: The start prompt.
    """
    is_revision = len(previous_reviews) > 0

    revision_context = ""
    if is_revision:
        revision_context = (
            "This is a REVISED manuscript. Please evaluate how well the authors have addressed previous concerns.\n\n"
            f"{format_previous_reviews(previous_reviews)}"
            f"{format_author_response(author_response)}"
        )

    return (
        f"This is an individual review session with {reviewer} to evaluate a scientific manuscript.\n\n"
        f"{revision_context}"
        f"{format_manuscript(manuscript_text)}"
        f"{format_review_criteria(review_criteria)}"
        f"{reviewer}, please provide your comprehensive review of this manuscript.\n\n"
        f"{review_structure_prompt()}"
    )


def individual_review_critic_prompt(critic: Agent, reviewer: Agent) -> str:
    """Generates the critic prompt for an individual review.

    :param critic: The critic.
    :param reviewer: The reviewer being critiqued.
    :return: The critic prompt.
    """
    return (
        f"{critic.title}, please critique {reviewer.title}'s review. "
        f"Is the review thorough and fair? Are there important issues the reviewer missed? "
        f"Is the feedback specific and actionable? "
        f"Suggest improvements to make the review more helpful to the authors. "
        f"Only provide feedback; do not write the review yourself."
    )


def individual_review_revision_prompt(critic: Agent, reviewer: Agent) -> str:
    """Generates the prompt for the reviewer to revise based on critic feedback.

    :param critic: The critic.
    :param reviewer: The reviewer.
    :return: The revision prompt.
    """
    return (
        f"{reviewer.title}, please revise your review based on {critic.title}'s feedback. "
        f"Address the issues raised and improve your review accordingly."
    )


# =============================================================================
# Default Review Criteria for Biomedical Manuscripts
# =============================================================================

BIOMEDICAL_REVIEW_CRITERIA = (
    "Scientific rigor: Are the methods appropriate and well-executed?",
    "Novelty: Does this work represent a significant advance over existing literature?",
    "Significance: Will this work have an impact on the field?",
    "Data quality: Are the data convincing and properly analyzed?",
    "Reproducibility: Are sufficient details provided to reproduce the experiments?",
    "Claims vs. evidence: Are all claims supported by the presented data?",
    "Presentation: Is the manuscript clearly written and well-organized?",
    "Figures and tables: Are they clear, informative, and properly labeled?",
    "Ethics: Are there any ethical concerns with the research?",
)
