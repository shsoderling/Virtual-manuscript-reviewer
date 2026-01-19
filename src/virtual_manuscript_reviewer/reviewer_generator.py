"""Dynamic reviewer generation based on manuscript content."""

from __future__ import annotations

import json
from typing import List, Tuple

from openai import OpenAI

from virtual_manuscript_reviewer.agent import Agent
from virtual_manuscript_reviewer.constants import DEFAULT_MODEL, CONSISTENT_TEMPERATURE


def generate_reviewers_for_manuscript(
    manuscript_text: str,
    num_reviewers: int = 3,
    model: str = DEFAULT_MODEL,
) -> Tuple[Agent, ...]:
    """Analyze manuscript content and generate specialized reviewers.

    :param manuscript_text: The manuscript content (abstract + text).
    :param num_reviewers: Number of reviewers to generate (default 3).
    :param model: The LLM model to use for analysis.
    :return: Tuple of Agent objects with specialized expertise.
    """
    client = OpenAI()

    # Create a prompt to analyze the manuscript and suggest reviewers
    analysis_prompt = f"""Analyze this scientific manuscript and identify {num_reviewers} specialized reviewer profiles that would be ideal for peer review.

Consider:
1. The main research techniques/methods used (e.g., proteomics, CRISPR, imaging, behavioral assays)
2. The biological/scientific domain (e.g., neuroscience, cancer biology, immunology)
3. Any specialized expertise needed (e.g., bioinformatics, specific animal models, clinical relevance)

For each reviewer, provide:
- A specific title (e.g., "Proteomics Specialist" not just "Methodology Reviewer")
- Their precise expertise relevant to THIS manuscript
- Their goal in reviewing this specific paper
- Their role in evaluating specific aspects

Return your response as a JSON array with exactly {num_reviewers} reviewer objects.
Each object must have these exact fields: "title", "expertise", "goal", "role"

Example format:
[
  {{
    "title": "Synaptic Biology Expert",
    "expertise": "synaptic vesicle dynamics, SNARE complex function, and presynaptic protein interactions",
    "goal": "evaluate the accuracy of synaptic biology claims and the appropriateness of synaptic assays",
    "role": "assess whether the synaptic phenotypes are properly characterized and interpreted in the context of current literature"
  }},
  ...
]

Here is the manuscript to analyze:

{manuscript_text[:15000]}

Return ONLY the JSON array, no other text."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are an expert at identifying the ideal peer reviewers for scientific manuscripts. You understand the nuances of different research fields and can identify the specific expertise needed to properly evaluate a paper."
            },
            {
                "role": "user",
                "content": analysis_prompt
            }
        ],
        temperature=CONSISTENT_TEMPERATURE,
    )

    # Parse the response
    response_text = response.choices[0].message.content or ""

    # Try to extract JSON from the response
    try:
        # Handle case where response might have markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        reviewer_data = json.loads(response_text.strip())
    except json.JSONDecodeError:
        # Fallback to default reviewers if parsing fails
        print("Warning: Could not parse reviewer suggestions, using defaults")
        from virtual_manuscript_reviewer.prompts import DEFAULT_REVIEWERS
        return DEFAULT_REVIEWERS

    # Create Agent objects from the parsed data
    reviewers = []
    for reviewer in reviewer_data[:num_reviewers]:
        try:
            agent = Agent(
                title=reviewer["title"],
                expertise=reviewer["expertise"],
                goal=reviewer["goal"],
                role=reviewer["role"],
                model=model,
            )
            reviewers.append(agent)
        except KeyError as e:
            print(f"Warning: Missing field {e} in reviewer data, skipping")
            continue

    # If we didn't get enough reviewers, fill with defaults
    if len(reviewers) < num_reviewers:
        from virtual_manuscript_reviewer.prompts import DEFAULT_REVIEWERS
        for default_reviewer in DEFAULT_REVIEWERS:
            if len(reviewers) >= num_reviewers:
                break
            # Check if we already have a similar reviewer
            if not any(r.title == default_reviewer.title for r in reviewers):
                reviewers.append(default_reviewer)

    return tuple(reviewers)


def print_reviewer_panel(reviewers: Tuple[Agent, ...]) -> None:
    """Print the reviewer panel for user visibility.

    :param reviewers: The tuple of reviewer agents.
    """
    print("\n" + "=" * 60)
    print("GENERATED REVIEWER PANEL")
    print("=" * 60)
    for i, reviewer in enumerate(reviewers, 1):
        print(f"\nReviewer {i}: {reviewer.title}")
        print(f"  Expertise: {reviewer.expertise}")
        print(f"  Goal: {reviewer.goal}")
    print("=" * 60 + "\n")
