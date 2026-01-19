"""Utility functions for the manuscript reviewer."""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict, Tuple

import ssl
import warnings
import certifi
import requests
from urllib3.exceptions import InsecureRequestWarning
import tiktoken

# Suppress SSL warnings when using fallback
warnings.filterwarnings("ignore", category=InsecureRequestWarning)
from openai.types.chat import ChatCompletionMessageParam
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall

from virtual_manuscript_reviewer.constants import (
    MODEL_TO_INPUT_PRICE_PER_TOKEN,
    MODEL_TO_OUTPUT_PRICE_PER_TOKEN,
    PUBMED_TOOL_NAME,
)


def get_pubmed_central_article(pmcid: str, abstract_only: bool = False) -> tuple[str | None, list[str] | None]:
    """Gets the title and content of a PubMed Central article given a PMC ID.

    :param pmcid: The PMC ID of the article.
    :param abstract_only: Whether to return only the abstract.
    :return: The title and content or None if not found.
    """
    text_url = f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_JSON/PMC{pmcid}/unicode"
    try:
        response = requests.get(text_url, verify=certifi.where())
        response.raise_for_status()
    except requests.exceptions.SSLError:
        # Fallback: try without SSL verification (less secure but functional)
        response = requests.get(text_url, verify=False)
        response.raise_for_status()

    try:
        article = response.json()
    except json.JSONDecodeError:
        return None, None

    document = article[0]["documents"][0]
    title = next(
        passage["text"]
        for passage in document["passages"]
        if passage["infons"]["section_type"] == "TITLE"
    )

    passages = [
        passage
        for passage in document["passages"]
        if passage["infons"]["type"] in {"abstract", "paragraph"}
    ]

    if abstract_only:
        passages = [
            passage
            for passage in passages
            if passage["infons"]["section_type"] in ["ABSTRACT"]
        ]
    else:
        passages = [
            passage
            for passage in passages
            if passage["infons"]["section_type"]
            in ["ABSTRACT", "INTRO", "RESULTS", "DISCUSS", "CONCL", "METHODS"]
        ]

    content = [passage["text"] for passage in passages]

    return title, content


def run_pubmed_search(query: str, num_articles: int = 3, abstract_only: bool = False) -> str:
    """Runs a PubMed search, returning article content.

    :param query: The search query.
    :param num_articles: Number of articles to retrieve.
    :param abstract_only: Whether to return only abstracts.
    :return: Formatted article content.
    """
    print(
        f'Searching PubMed Central for {num_articles} articles '
        f'({"abstracts" if abstract_only else "full text"}) with query: "{query}"'
    )

    search_url = (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
        f"db=pmc&term={urllib.parse.quote_plus(query)}&retmax={2 * num_articles}&retmode=json&sort=relevance"
    )
    try:
        response = requests.get(search_url, verify=certifi.where())
        response.raise_for_status()
    except requests.exceptions.SSLError:
        # Fallback: try without SSL verification
        response = requests.get(search_url, verify=False)
        response.raise_for_status()
    pmcids_found = response.json()["esearchresult"]["idlist"]

    texts = []
    titles = []
    pmcids = []

    for pmcid in pmcids_found:
        if len(pmcids) >= num_articles:
            break

        title, content = get_pubmed_central_article(
            pmcid=pmcid,
            abstract_only=abstract_only,
        )

        if title is None:
            continue

        texts.append(f"PMCID = {pmcid}\n\nTitle = {title}\n\n{chr(10).join(content or [])}")
        titles.append(title)
        pmcids.append(pmcid)

    article_count = len(texts)
    print(f"Found {article_count:,} articles on PubMed Central")

    if article_count == 0:
        return f'No articles found on PubMed Central for the query "{query}".'

    formatted_articles = []
    for i, text in enumerate(texts):
        formatted_articles.append(f"[begin article {i + 1}]\n\n{text}\n\n[end article {i + 1}]")

    intro = f'Here are the top {article_count} articles on PubMed Central for the query "{query}":'
    return f"{intro}\n\n{''.join(formatted_articles)}"


def run_tools(
    tool_calls: list[ChatCompletionMessageToolCall],
) -> tuple[list[str], list[ChatCompletionMessageParam]]:
    """Runs the tools from chat completion tool calls.

    :param tool_calls: The tool calls from the chat completion response.
    :return: A tuple of (tool outputs, tool response messages).
    """
    tool_outputs: list[str] = []
    tool_messages: list[ChatCompletionMessageParam] = []

    for tool_call in tool_calls:
        if tool_call.function.name == PUBMED_TOOL_NAME:
            args_dict = json.loads(tool_call.function.arguments)
            output = run_pubmed_search(**args_dict)
            tool_outputs.append(output)

            tool_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output,
            })
        else:
            raise ValueError(f"Unknown tool: {tool_call.function.name}")

    return tool_outputs, tool_messages


def count_tokens(string: str, encoding_name: str = "cl100k_base") -> int:
    """Returns the number of tokens in a text string.

    :param string: The text string.
    :param encoding_name: The encoding name.
    :return: The token count.
    """
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(string))


def update_token_counts(
    token_counts: dict[str, int],
    discussion: list[dict[str, str]],
    response: str,
) -> None:
    """Updates the token counts with a discussion and response.

    :param token_counts: The token counts to update.
    :param discussion: The discussion.
    :param response: The response.
    """
    new_input_token_count = sum(count_tokens(turn["message"]) for turn in discussion)
    new_output_token_count = count_tokens(response)

    token_counts["input"] += new_input_token_count
    token_counts["output"] += new_output_token_count
    token_counts["max"] = max(
        token_counts["max"], new_input_token_count + new_output_token_count
    )


def count_discussion_tokens(discussion: list[dict[str, str]]) -> dict[str, int]:
    """Counts the number of tokens in a discussion.

    :param discussion: The discussion.
    :return: Token counts dictionary.
    """
    token_counts = {"input": 0, "output": 0, "max": 0}

    for index, turn in enumerate(discussion):
        if turn["agent"] != "User":
            update_token_counts(
                token_counts=token_counts,
                discussion=discussion[:index],
                response=turn["message"],
            )

    return token_counts


def _find_model_price_key(model: str, price_dict: dict[str, float]) -> str | None:
    """Finds the matching key in a price dictionary for a model.

    :param model: The model name.
    :param price_dict: The price dictionary.
    :return: The matching key or None.
    """
    if model in price_dict:
        return model

    matching_keys = [key for key in price_dict if model.startswith(key)]
    if matching_keys:
        return max(matching_keys, key=len)

    return None


def compute_token_cost(model: str, input_token_count: int, output_token_count: int) -> float:
    """Computes the token cost of a model.

    :param model: The model name.
    :param input_token_count: Input tokens.
    :param output_token_count: Output tokens.
    :return: The cost in USD.
    """
    input_key = _find_model_price_key(model, MODEL_TO_INPUT_PRICE_PER_TOKEN)
    output_key = _find_model_price_key(model, MODEL_TO_OUTPUT_PRICE_PER_TOKEN)

    if input_key is None or output_key is None:
        raise ValueError(f'Cost of model "{model}" not known')

    return (
        input_token_count * MODEL_TO_INPUT_PRICE_PER_TOKEN[input_key]
        + output_token_count * MODEL_TO_OUTPUT_PRICE_PER_TOKEN[output_key]
    )


def print_cost_and_time(
    token_counts: dict[str, int],
    model: str,
    elapsed_time: float,
) -> None:
    """Prints token counts, cost, and time.

    :param token_counts: The token counts.
    :param model: The model name.
    :param elapsed_time: Elapsed time in seconds.
    """
    print(f"Input token count: {token_counts['input']:,}")
    print(f"Output token count: {token_counts['output']:,}")
    print(f"Tool token count: {token_counts.get('tool', 0):,}")
    print(f"Max token length: {token_counts['max']:,}")

    try:
        cost = compute_token_cost(
            model=model,
            input_token_count=token_counts["input"] + token_counts.get("tool", 0),
            output_token_count=token_counts["output"],
        )
        print(f"Cost: ${cost:.2f}")
    except ValueError as e:
        print(f"Warning: {e}")

    print(f"Time: {int(elapsed_time // 60)}:{int(elapsed_time % 60):02d}")


def get_summary(discussion: list[dict[str, str]]) -> str:
    """Get the summary from a discussion.

    :param discussion: The discussion.
    :return: The summary (last message).
    """
    return discussion[-1]["message"]


def save_review(
    save_dir: Path,
    save_name: str,
    discussion: list[dict[str, str]],
    manuscript_title: str = "",
    generate_pdf: bool = True,
    pdf_output_dir: Optional[Path] = None,
) -> dict[str, Path]:
    """Save a review discussion to JSON, Markdown, and optionally PDF files.

    :param save_dir: The directory to save JSON and MD files.
    :param save_name: The file name.
    :param discussion: The discussion.
    :param manuscript_title: The manuscript title for PDF generation.
    :param generate_pdf: Whether to generate a PDF.
    :param pdf_output_dir: Directory for PDF output (defaults to user Downloads).
    :return: Dictionary of paths to saved files.
    """
    save_dir.mkdir(parents=True, exist_ok=True)

    saved_files: dict[str, Path] = {}

    # Save as JSON
    json_path = save_dir / f"{save_name}.json"
    with open(json_path, "w") as f:
        json.dump(discussion, f, indent=4)
    saved_files["json"] = json_path

    # Save as Markdown
    md_path = save_dir / f"{save_name}.md"
    with open(md_path, "w", encoding="utf-8") as file:
        for turn in discussion:
            file.write(f"## {turn['agent']}\n\n{turn['message']}\n\n")
    saved_files["markdown"] = md_path

    # Generate PDF
    if generate_pdf:
        try:
            from virtual_manuscript_reviewer.pdf_generator import generate_review_pdf

            # Default to user Downloads folder
            if pdf_output_dir is None:
                pdf_output_dir = Path.home() / "Downloads"

            pdf_output_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = pdf_output_dir / f"{save_name}_review.pdf"

            generate_review_pdf(
                discussion=discussion,
                manuscript_title=manuscript_title or save_name,
                output_path=pdf_path,
                include_full_discussion=False,
            )
            saved_files["pdf"] = pdf_path
            print(f"Review PDF saved to: {pdf_path}")
        except ImportError as e:
            print(f"Warning: Could not generate PDF (missing reportlab): {e}")
        except Exception as e:
            print(f"Warning: PDF generation failed: {e}")

    return saved_files


def load_review_summary(review_path: Path) -> str:
    """Load a review summary from a JSON file.

    :param review_path: Path to the review JSON file.
    :return: The review summary.
    """
    with open(review_path, "r") as f:
        discussion = json.load(f)
    return get_summary(discussion)


def load_review_summaries(review_paths: list[Path]) -> tuple[str, ...]:
    """Load multiple review summaries.

    :param review_paths: Paths to review JSON files.
    :return: Tuple of review summaries.
    """
    return tuple(load_review_summary(path) for path in review_paths)
