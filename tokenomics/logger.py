from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = PROJECT_ROOT / "tokenomics_log.jsonl"

load_dotenv(PROJECT_ROOT / ".env")


def get_rate(variable_name: str) -> float:
    value = os.getenv(variable_name)

    if value is None:
        raise RuntimeError(
            f"{variable_name} is missing from the .env file."
        )

    rate = float(value)

    if rate < 0:
        raise ValueError(f"{variable_name} cannot be negative.")

    return rate


def log(
    query: str,
    agent: str,
    input_tokens: int,
    output_tokens: int,
) -> dict:
    input_tokens = max(0, int(input_tokens or 0))
    output_tokens = max(0, int(output_tokens or 0))

    input_rate = get_rate("GEMINI_INPUT_COST_PER_1M")
    output_rate = get_rate("GEMINI_OUTPUT_COST_PER_1M")

    input_cost = (input_tokens / 1_000_000) * input_rate
    output_cost = (output_tokens / 1_000_000) * output_rate
    total_cost = input_cost + output_cost

    entry = {
        "timestamp": datetime.now().astimezone().isoformat(),
        "query": query,
        "agent": agent,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(total_cost, 6),
        "cost_per_1m_queries": round(total_cost * 1_000_000, 2),
    }

    print(
        f"\n[TOKENOMICS] Agent: {agent} | "
        f"Input: {input_tokens} | "
        f"Output: {output_tokens} | "
        f"Cost: ${total_cost:.6f}"
    )

    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry) + "\n")

    return entry
