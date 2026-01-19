"""Runs a manuscript review with LLM agents."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Literal, List, Dict, Optional, Union, Tuple

from openai import OpenAI, NOT_GIVEN
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
from tqdm import trange, tqdm

from virtual_manuscript_reviewer.agent import Agent
from virtual_manuscript_reviewer.constants import CONSISTENT_TEMPERATURE, PUBMED_TOOL_DESCRIPTION
from virtual_manuscript_reviewer.manuscript import Manuscript
from virtual_manuscript_reviewer.prompts import (
    EDITOR,
    SCIENTIFIC_CRITIC,
    DEFAULT_REVIEWERS,
    BIOMEDICAL_REVIEW_CRITERIA,
    individual_review_start_prompt,
    individual_review_critic_prompt,
    individual_review_revision_prompt,
    review_meeting_start_prompt,
    review_meeting_editor_initial_prompt,
    review_meeting_editor_intermediate_prompt,
    review_meeting_editor_final_prompt,
    review_meeting_reviewer_prompt,
)
from virtual_manuscript_reviewer.utils import (
    count_discussion_tokens,
    count_tokens,
    get_summary,
    print_cost_and_time,
    run_tools,
    save_review,
)


def run_review(
    manuscript: Manuscript | str,
    review_type: Literal["panel", "individual"] = "panel",
    save_dir: Path | str = Path("reviews"),
    save_name: str = "review",
    editor: Agent | None = None,
    reviewers: tuple[Agent, ...] | None = None,
    reviewer: Agent | None = None,
    review_criteria: tuple[str, ...] = BIOMEDICAL_REVIEW_CRITERIA,
    previous_reviews: tuple[str, ...] = (),
    author_response: str = "",
    num_rounds: int = 1,
    temperature: float = CONSISTENT_TEMPERATURE,
    pubmed_search: bool = True,
    return_summary: bool = False,
    auto_generate_reviewers: bool = True,
    generate_pdf: bool = True,
    run_mentor: bool = True,
) -> str | None:
    """Runs a manuscript review with LLM agents.

    :param manuscript: The manuscript to review (Manuscript object or text string).
    :param review_type: The type of review ("panel" for multi-reviewer, "individual" for single).
    :param save_dir: Directory to save the review.
    :param save_name: Name for the saved review files.
    :param editor: The editor for panel reviews (uses default if None).
    :param reviewers: The reviewer panel for panel reviews (uses defaults if None).
    :param reviewer: The reviewer for individual reviews.
    :param review_criteria: Criteria to evaluate the manuscript on.
    :param previous_reviews: Previous review summaries (for revision tracking).
    :param author_response: Authors' response to previous reviews.
    :param num_rounds: Number of discussion rounds.
    :param temperature: Sampling temperature.
    :param pubmed_search: Whether to enable PubMed search tool.
    :param return_summary: Whether to return the review summary.
    :param generate_pdf: Whether to generate PDF output in Downloads folder.
    :param run_mentor: Whether to run the scientific mentor after review.
    :return: The review summary if return_summary is True, else None.
    """
    # Convert save_dir to Path if needed
    save_dir = Path(save_dir)

    # Get manuscript text
    if isinstance(manuscript, Manuscript):
        manuscript_text = manuscript.get_review_context()
    else:
        manuscript_text = manuscript

    # Validate review type and set defaults
    if review_type == "panel":
        if editor is None:
            editor = EDITOR
        if reviewers is None:
            if auto_generate_reviewers:
                # Dynamically generate reviewers based on manuscript content
                from virtual_manuscript_reviewer.reviewer_generator import (
                    generate_reviewers_for_manuscript,
                    print_reviewer_panel,
                )
                print("Analyzing manuscript to generate specialized reviewers...")
                reviewers = generate_reviewers_for_manuscript(manuscript_text)
                print_reviewer_panel(reviewers)
            else:
                reviewers = DEFAULT_REVIEWERS
        if len(reviewers) == 0:
            raise ValueError("Panel review requires at least one reviewer")
        if reviewer is not None:
            raise ValueError("Panel review does not use individual reviewer parameter")
        if editor in reviewers:
            raise ValueError("Editor must be separate from reviewers")
        if len(set(reviewers)) != len(reviewers):
            raise ValueError("Reviewers must be unique")
    elif review_type == "individual":
        if reviewer is None:
            raise ValueError("Individual review requires a reviewer")
        if editor is not None or reviewers is not None:
            raise ValueError("Individual review does not use editor or reviewers parameters")
    else:
        raise ValueError(f"Invalid review type: {review_type}")

    # Start timing
    start_time = time.time()

    # Set up OpenAI client
    client = OpenAI()

    # Set up team
    if review_type == "panel":
        assert editor is not None and reviewers is not None
        team: list[Agent] = [editor] + list(reviewers)
        primary_model = editor.model
    else:
        assert reviewer is not None
        team = [reviewer, SCIENTIFIC_CRITIC]
        primary_model = reviewer.model

    # Set up tools
    tools: list[ChatCompletionToolParam] | None = (
        [ChatCompletionToolParam(**PUBMED_TOOL_DESCRIPTION)] if pubmed_search else None  # type: ignore[misc]
    )

    # Initialize tracking
    tool_token_count = 0
    discussion: list[dict[str, str]] = []
    messages: list[ChatCompletionMessageParam] = []

    # Initial prompt
    if review_type == "panel":
        assert editor is not None and reviewers is not None
        initial_content = review_meeting_start_prompt(
            editor=editor,
            reviewers=reviewers,
            manuscript_text=manuscript_text,
            review_criteria=review_criteria,
            previous_reviews=previous_reviews,
            author_response=author_response,
            num_rounds=num_rounds,
        )
        messages.append({"role": "user", "content": initial_content})
        discussion.append({"agent": "User", "message": initial_content})

    # Loop through rounds
    for round_index in trange(num_rounds + 1, desc="Rounds (+ Final Round)"):
        round_num = round_index + 1

        # Loop through team
        for agent in tqdm(team, desc="Reviewers"):
            # Generate prompt based on agent and round
            if review_type == "panel":
                assert editor is not None
                if agent == editor:
                    if round_index == 0:
                        prompt = review_meeting_editor_initial_prompt(editor=editor)
                    elif round_index == num_rounds:
                        prompt = review_meeting_editor_final_prompt(
                            editor=editor,
                            review_criteria=review_criteria,
                        )
                    else:
                        prompt = review_meeting_editor_intermediate_prompt(
                            editor=editor,
                            round_num=round_num - 1,
                            num_rounds=num_rounds,
                        )
                else:
                    prompt = review_meeting_reviewer_prompt(
                        reviewer=agent,
                        round_num=round_num,
                        num_rounds=num_rounds,
                    )
            else:
                assert reviewer is not None
                if agent == SCIENTIFIC_CRITIC:
                    prompt = individual_review_critic_prompt(
                        critic=SCIENTIFIC_CRITIC,
                        reviewer=reviewer,
                    )
                else:
                    if round_index == 0:
                        prompt = individual_review_start_prompt(
                            reviewer=reviewer,
                            manuscript_text=manuscript_text,
                            review_criteria=review_criteria,
                            previous_reviews=previous_reviews,
                            author_response=author_response,
                        )
                    else:
                        prompt = individual_review_revision_prompt(
                            critic=SCIENTIFIC_CRITIC,
                            reviewer=reviewer,
                        )

            # Add prompt as user message
            messages.append({"role": "user", "content": prompt})
            discussion.append({"agent": "User", "message": prompt})

            # Build messages with agent's system prompt
            agent_messages: list[ChatCompletionMessageParam] = [agent.message] + messages

            # Call the API
            response = client.chat.completions.create(
                model=agent.model,
                messages=agent_messages,
                temperature=temperature,
                tools=tools if tools else NOT_GIVEN,
            )

            response_message = response.choices[0].message

            # Handle tool calls
            if response_message.tool_calls:
                tool_outputs, tool_messages = run_tools(tool_calls=response_message.tool_calls)
                tool_token_count += sum(count_tokens(output) for output in tool_outputs)

                # Add assistant message with tool calls
                assistant_tool_message: ChatCompletionAssistantMessageParam = {
                    "role": "assistant",
                    "content": response_message.content,
                    "tool_calls": [tc.model_dump() for tc in response_message.tool_calls],  # type: ignore[misc]
                }
                messages.append(assistant_tool_message)

                # Add tool responses
                for tool_msg in tool_messages:
                    messages.append(tool_msg)

                # Add to discussion
                tool_output_content = "\n\n".join(tool_outputs)
                discussion.append({"agent": "Tool", "message": tool_output_content})

                # Make follow-up API call
                agent_messages = [agent.message] + messages
                response = client.chat.completions.create(
                    model=agent.model,
                    messages=agent_messages,
                    temperature=temperature,
                )
                response_message = response.choices[0].message

            # Extract response
            response_content = response_message.content or ""

            # Add to messages and discussion
            messages.append({"role": "assistant", "content": response_content})
            discussion.append({"agent": agent.title, "message": response_content})

            # Final round: only editor/reviewer responds
            if round_index == num_rounds:
                break

    # Count tokens
    token_counts = count_discussion_tokens(discussion=discussion)
    token_counts["tool"] = tool_token_count

    # Print stats
    print_cost_and_time(
        token_counts=token_counts,
        model=primary_model,
        elapsed_time=time.time() - start_time,
    )

    # Get manuscript title for PDF
    manuscript_title = ""
    if isinstance(manuscript, Manuscript):
        manuscript_title = manuscript.title

    # Save the review
    save_review(
        save_dir=save_dir,
        save_name=save_name,
        discussion=discussion,
        manuscript_title=manuscript_title,
        generate_pdf=generate_pdf,
    )

    # Get review summary
    review_summary = get_summary(discussion)

    # Run scientific mentor if requested
    if run_mentor and review_summary:
        try:
            from virtual_manuscript_reviewer.scientific_mentor import (
                run_scientific_mentor,
                save_mentor_report,
            )
            from virtual_manuscript_reviewer.pdf_generator import generate_mentor_pdf

            mentor_report = run_scientific_mentor(
                review_summary=review_summary,
                manuscript_text=manuscript_text,
                temperature=temperature,
            )

            # Save mentor report as markdown
            mentor_md_path = save_dir / f"{save_name}_mentor.md"
            save_mentor_report(mentor_report, mentor_md_path)

            # Save mentor report as PDF to Downloads
            if generate_pdf:
                pdf_output_dir = Path.home() / "Downloads"
                mentor_pdf_path = pdf_output_dir / f"{save_name}_mentor.pdf"
                generate_mentor_pdf(
                    mentor_report=mentor_report,
                    manuscript_title=manuscript_title,
                    output_path=mentor_pdf_path,
                )
                print(f"Mentor PDF saved to: {mentor_pdf_path}")

        except ImportError as e:
            print(f"Warning: Could not run scientific mentor: {e}")
        except Exception as e:
            print(f"Warning: Scientific mentor failed: {e}")

    # Return summary if requested
    if return_summary:
        return review_summary

    return None


def review_manuscript(
    pdf_path: str | Path,
    save_dir: str | Path = "reviews",
    review_criteria: tuple[str, ...] = BIOMEDICAL_REVIEW_CRITERIA,
    num_rounds: int = 1,
) -> str:
    """Convenience function to review a manuscript PDF.

    :param pdf_path: Path to the PDF file.
    :param save_dir: Directory to save the review.
    :param review_criteria: Review criteria to use.
    :param num_rounds: Number of discussion rounds.
    :return: The review summary.
    """
    # Load manuscript
    manuscript = Manuscript.from_pdf(pdf_path)
    print(f"Loaded manuscript: {manuscript.title}")
    print(f"Version hash: {manuscript.version_hash}")

    # Generate save name from manuscript
    safe_title = "".join(c if c.isalnum() or c in "- " else "_" for c in manuscript.title[:50])
    save_name = f"{safe_title}_{manuscript.version_hash}"

    # Run review
    summary = run_review(
        manuscript=manuscript,
        review_type="panel",
        save_dir=Path(save_dir),
        save_name=save_name,
        review_criteria=review_criteria,
        num_rounds=num_rounds,
        return_summary=True,
    )

    return summary or ""
