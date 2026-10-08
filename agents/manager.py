from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

import qualitative, quantitative
from tokenomics.logger import log
from validation.validator import (
    validate_qualitative,
    validate_quantitative,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY was not found in .env")

if not MODEL_NAME:
    raise RuntimeError("GEMINI_MODEL was not found in .env")

client = genai.Client(api_key=API_KEY)

ROUTING_INSTRUCTION = """
You are a query-routing assistant.

Classify each user request as exactly one lowercase word:

qualitative = policies, procedures, documentation, explanations,
or questions answered from retrieved documents

quantitative = numbers, metrics, trends, comparisons, or questions
answered by querying the SQLite database

both = questions that need both document retrieval and database analysis

Return only one word:
qualitative, quantitative, or both.
"""


def get_token_counts(interaction) -> tuple[int, int]:
    usage = getattr(interaction, "usage", None)

    if usage is None:
        return 0, 0

    input_tokens = getattr(usage, "total_input_tokens", None)
    output_tokens = getattr(usage, "total_output_tokens", None)

    if input_tokens is None:
        input_tokens = getattr(usage, "input_tokens", 0)

    if output_tokens is None:
        output_tokens = getattr(usage, "output_tokens", 0)

    return int(input_tokens or 0), int(output_tokens or 0)


def classify(query: str) -> str:
    if not query.strip():
        raise ValueError("Please enter a question.")

    interaction = client.interactions.create(
        model=MODEL_NAME,
        system_instruction=ROUTING_INSTRUCTION,
        input=f"Classify this query:\n\n{query}",
    )

    route = interaction.output_text.strip().lower()
    route = route.strip(" .`")

    input_tokens, output_tokens = get_token_counts(interaction)

    log(
        query=query,
        agent="manager-classifier",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    valid_routes = {"qualitative", "quantitative", "both"}

    if route in valid_routes:
        return route

    return "qualitative"


def run(query: str) -> dict:
    route = classify(query)

    result = {
        "query": query,
        "route": route,
        "qualitative": None,
        "quantitative": None,
    }

    if route in {"qualitative", "both"}:
        qual_result = qualitative.run(query)

        validation = validate_qualitative(
            answer=qual_result["answer"],
            chunks=qual_result["chunks"],
        )

        log(
            query=query,
            agent="qualitative",
            input_tokens=qual_result.get("input_tokens", 0),
            output_tokens=qual_result.get("output_tokens", 0),
        )

        if validation["flag"]:
            displayed_answer = (
                "I cannot provide a grounded answer because the response "
                "did not cite the retrieved documents."
            )
        else:
            displayed_answer = qual_result["answer"]

        result["qualitative"] = {
            "answer": displayed_answer,
            "sources_cited": validation["sources_cited"],
            "validation": validation,
        }

    if route in {"quantitative", "both"}:
        quant_result = quantitative.run(query)

        validation = validate_quantitative(
            answer=quant_result["answer"],
            sql=quant_result["sql"],
            validation_status=quant_result["validation"],
        )

        log(
            query=query,
            agent="quantitative",
            input_tokens=quant_result.get("input_tokens", 0),
            output_tokens=quant_result.get("output_tokens", 0),
        )

        if validation["flag"]:
            displayed_answer = (
                "I cannot provide a validated data answer. "
                f"{validation['warning']}"
            )
            displayed_sql = None
        else:
            displayed_answer = quant_result["answer"]
            displayed_sql = quant_result["sql"]

        result["quantitative"] = {
            "answer": displayed_answer,
            "sql": displayed_sql,
            "validation": validation,
        }

    return result


def print_result(result: dict) -> None:
    print(f"\nQuery: {result['query']}")
    print(f"Route: {result['route']}")

    qualitative_result = result["qualitative"]

    if qualitative_result:
        print("\n[Qualitative]")
        print(qualitative_result["answer"])

        sources = qualitative_result["sources_cited"]
        if sources:
            print(f"Sources cited: {', '.join(sources)}")

        warning = qualitative_result["validation"]["warning"]
        if warning:
            print(f"Validation warning: {warning}")

    quantitative_result = result["quantitative"]

    if quantitative_result:
        print("\n[Quantitative]")
        print(quantitative_result["answer"])

        if quantitative_result["sql"]:
            print(f"SQL used: {quantitative_result['sql']}")

        warning = quantitative_result["validation"]["warning"]
        if warning:
            print(f"Validation warning: {warning}")


if __name__ == "__main__":
    question = input("Ask a question: ").strip()

    if question:
        print_result(run(question))
    else:
        print("No question entered.")
