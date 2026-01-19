"""Scientific mentor agent that provides guidance on addressing reviewer concerns."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from openai import OpenAI

from virtual_manuscript_reviewer.agent import Agent
from virtual_manuscript_reviewer.constants import DEFAULT_MODEL, CONSISTENT_TEMPERATURE
from virtual_manuscript_reviewer.utils import count_tokens, print_cost_and_time


# Scientific Mentor Agent
SCIENTIFIC_MENTOR = Agent(
    title="Scientific Mentor",
    expertise="guiding early-career scientists through the peer review process, manuscript revision strategy, and experimental design",
    goal="provide clear, actionable guidance to help authors successfully address reviewer concerns and improve their manuscript",
    role="act as a supportive mentor who helps authors understand reviewer feedback, prioritize revisions, and develop both textual changes and experimental plans to strengthen their work",
    model=DEFAULT_MODEL,
)


MENTOR_SYSTEM_PROMPT = """You are an experienced scientific mentor helping authors respond to peer review.
Your role is to provide practical, actionable guidance that helps authors:
1. Understand the core concerns behind reviewer comments
2. Prioritize which issues to address first
3. Develop both textual revisions and experimental plans

You should be supportive but realistic about what can be achieved. When experiments are suggested,
consider feasibility, time, and resources. Always aim to help the authors produce the strongest
possible revision while being mindful of practical constraints.

Structure your advice to be clear and actionable, with specific recommendations the authors can follow."""


def generate_mentor_prompt(review_summary: str, manuscript_text: str) -> str:
    """Generate the prompt for the scientific mentor.

    :param review_summary: The review summary from the panel.
    :param manuscript_text: The original manuscript text.
    :return: The mentor prompt.
    """
    return f"""As a scientific mentor, please review the following peer review feedback and provide comprehensive guidance to help the authors address the reviewer concerns.

## Review Summary

{review_summary}

## Original Manuscript (for reference)

[The manuscript being reviewed has been provided to you for context.]

---

Please provide your mentorship guidance in the following structure:

## Executive Summary
Briefly summarize the overall reviewer sentiment and the key issues that must be addressed for successful revision.

## Priority Assessment
Categorize the reviewer concerns by priority:
- **Critical (Must Address)**: Issues that will likely result in rejection if not addressed
- **Important (Should Address)**: Issues that significantly strengthen the paper
- **Minor (Nice to Address)**: Issues that are suggestions or polish

## Textual Revisions
For each major concern, provide specific guidance on how to revise the text:

### [Concern Category 1]
**Reviewer Concern**: [Summarize the concern]
**Recommended Textual Changes**:
- Specific text additions, deletions, or modifications
- Suggested wording or framing
- Where in the manuscript to make changes
**Example Language**: [Provide example text where helpful]

### [Concern Category 2]
[Continue for each major textual concern...]

## Experimental Recommendations
For concerns that require additional data or experiments:

### [Experimental Need 1]
**Reviewer Concern**: [What data/validation is needed]
**Recommended Experiments**:
- Specific experiments to perform
- Expected outcomes and how they address the concern
- Estimated difficulty/time (low/medium/high)
- Alternative approaches if primary experiment is not feasible

**If Not Feasible**: Suggested textual approach to acknowledge limitation

### [Experimental Need 2]
[Continue for each experimental need...]

## Response Letter Strategy
Provide guidance on how to structure the response to reviewers:
- Key points to emphasize
- Tone recommendations
- How to handle disagreements professionally

## Revision Checklist
A prioritized checklist of all changes to make:
- [ ] Critical item 1
- [ ] Critical item 2
- [ ] Important item 1
- [ ] Important item 2
- [ ] Minor item 1
[etc.]

## Estimated Revision Scope
Provide a realistic assessment:
- **Textual revisions only**: What can be achieved with writing changes alone
- **With additional analyses**: What becomes possible with reanalysis of existing data
- **With new experiments**: Full scope if all suggested experiments are performed

Please be specific, practical, and supportive in your guidance."""


def run_scientific_mentor(
    review_summary: str,
    manuscript_text: str,
    temperature: float = CONSISTENT_TEMPERATURE,
) -> str:
    """Run the scientific mentor to generate guidance.

    :param review_summary: The review summary from the panel.
    :param manuscript_text: The original manuscript text.
    :param temperature: Sampling temperature.
    :return: The mentor's guidance report.
    """
    print("\nGenerating Scientific Mentor guidance...")
    start_time = time.time()

    client = OpenAI()

    # Build messages
    messages = [
        {"role": "system", "content": f"{MENTOR_SYSTEM_PROMPT}\n\n{SCIENTIFIC_MENTOR.message['content']}"},
        {"role": "user", "content": generate_mentor_prompt(review_summary, manuscript_text)},
    ]

    # Call the API
    response = client.chat.completions.create(
        model=SCIENTIFIC_MENTOR.model,
        messages=messages,
        temperature=temperature,
    )

    mentor_report = response.choices[0].message.content or ""

    # Calculate and print stats
    input_tokens = sum(count_tokens(m.get("content", "")) for m in messages)
    output_tokens = count_tokens(mentor_report)

    token_counts = {
        "input": input_tokens,
        "output": output_tokens,
        "max": input_tokens + output_tokens,
    }

    print_cost_and_time(
        token_counts=token_counts,
        model=SCIENTIFIC_MENTOR.model,
        elapsed_time=time.time() - start_time,
    )

    return mentor_report


def save_mentor_report(
    mentor_report: str,
    save_path: Path,
) -> None:
    """Save the mentor report to a markdown file.

    :param mentor_report: The mentor's guidance report.
    :param save_path: Path to save the report.
    """
    save_path.parent.mkdir(parents=True, exist_ok=True)

    with open(save_path, "w", encoding="utf-8") as f:
        f.write("# Scientific Mentor Report\n\n")
        f.write("*Guidance for Addressing Reviewer Concerns*\n\n")
        f.write("---\n\n")
        f.write(mentor_report)

    print(f"Mentor report saved to: {save_path}")
