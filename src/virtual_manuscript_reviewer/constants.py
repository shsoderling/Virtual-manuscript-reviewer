"""Holds constants for the manuscript reviewer."""

# Use OpenAI's most capable model
DEFAULT_MODEL = "gpt-5.2-2025-12-11"

# Prices in USD (https://openai.com/api/pricing/)
MODEL_TO_INPUT_PRICE_PER_TOKEN = {
    "gpt-3.5-turbo-0125": 0.5 / 10**6,
    "gpt-4o-2024-08-06": 2.5 / 10**6,
    "gpt-4o-2024-05-13": 5 / 10**6,
    "gpt-4o-mini-2024-07-18": 0.15 / 10**6,
    "gpt-4o": 2.5 / 10**6,
    "gpt-4o-mini": 0.15 / 10**6,
    "o1-mini-2024-09-12": 3 / 10**6,
    "gpt-4.5-preview": 75 / 10**6,  # GPT-4.5/GPT-5 series
    "gpt-4.5-preview-2025-02-27": 75 / 10**6,
}

MODEL_TO_OUTPUT_PRICE_PER_TOKEN = {
    "gpt-3.5-turbo-0125": 1.5 / 10**6,
    "gpt-4o-2024-08-06": 10 / 10**6,
    "gpt-4o-2024-05-13": 15 / 10**6,
    "gpt-4o-mini-2024-07-18": 0.6 / 10**6,
    "gpt-4o": 10 / 10**6,
    "gpt-4o-mini": 0.6 / 10**6,
    "o1-mini-2024-09-12": 12 / 10**6,
    "gpt-4.5-preview": 150 / 10**6,  # GPT-4.5/GPT-5 series
    "gpt-4.5-preview-2025-02-27": 150 / 10**6,
}

# Temperature settings
CONSISTENT_TEMPERATURE = 0.2
CREATIVE_TEMPERATURE = 0.8

# PubMed tool for literature verification
PUBMED_TOOL_NAME = "pubmed_search"
PUBMED_TOOL_DESCRIPTION = {
    "type": "function",
    "function": {
        "name": PUBMED_TOOL_NAME,
        "description": "Search PubMed Central for biomedical articles to verify claims or find related work.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to use to search PubMed Central for scientific articles.",
                },
                "num_articles": {
                    "type": "integer",
                    "description": "The number of articles to return from the search query.",
                },
                "abstract_only": {
                    "type": "boolean",
                    "description": "Whether to return only the abstract of the articles.",
                },
            },
            "required": ["query", "num_articles"],
        },
    },
}

# Review structure sections
REVIEW_SECTIONS = [
    "Summary",
    "Major Strengths",
    "Major Weaknesses",
    "Minor Issues",
    "Specific Comments",
    "Recommendation",
]

# Recommendation options
RECOMMENDATIONS = [
    "Accept",
    "Minor Revisions",
    "Major Revisions",
    "Reject",
]
