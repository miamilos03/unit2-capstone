from __future__ import annotations

import os
import re
import sqlite3

from dotenv import load_dotenv
from google import genai


load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY was not found in .env")

if not MODEL:
    raise RuntimeError("GEMINI_MODEL was not found in .env")

client = genai.Client(api_key=API_KEY)

SCHEMA_CONTEXT = """
Available tables:

- sales(id, region, product, revenue, date, units_sold)
- customers(id, name, industry, churn_date, satisfaction_score)
- employees(id, department, satisfaction_score, tenure_years)
"""

SQL_SYSTEM_INSTRUCTION = """
You translate natural-language questions into SQLite SQL.

Rules:
- Return exactly one SQL query.
- Return only a SELECT query.
- Do not use Markdown code fences.
- Do not use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, ATTACH, or PRAGMA.
- Use only the tables and columns provided.
"""

INTERPRETATION_SYSTEM_INSTRUCTION = """
You interpret SQLite query results clearly and concisely.

Use only the supplied question, SQL query, columns, and results.
Do not invent information.
If no rows were returned, say that no matching records were found.
"""


def get_text(response) -> str:
    text = getattr(response, "output_text", None)

    if text:
        return text.strip()

    outputs = getattr(response, "outputs", [])

    for output in reversed(outputs):
        text = getattr(output, "text", None)

        if text:
            return text.strip()

    raise RuntimeError("Gemini returned no text.")


def get_token_counts(response) -> tuple[int, int]:
    usage = getattr(response, "usage", None)

    if usage is None:
        usage = getattr(response, "usage_metadata", None)

    if usage is None:
        return 0, 0

    input_tokens = getattr(usage, "input_tokens", None)

    if input_tokens is None:
        input_tokens = getattr(usage, "prompt_token_count", 0)

    output_tokens = getattr(usage, "output_tokens", None)

    if output_tokens is None:
        output_tokens = getattr(usage, "candidates_token_count", 0)

    return input_tokens or 0, output_tokens or 0


def ask_gemini(system_instruction: str, prompt: str) -> tuple[str, int, int]:
    response = client.interactions.create(
        model=MODEL,
        system_instruction=system_instruction,
        input=prompt,
    )

    text = get_text(response)
    input_tokens, output_tokens = get_token_counts(response)

    return text, input_tokens, output_tokens


def clean_sql(query: str) -> str:
    sql = query.strip()
    sql = re.sub(r"^```sql\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"^```\s*", "", sql)
    sql = re.sub(r"\s*```$", "", sql)

    return sql.strip().rstrip(";").strip()


def validate_sql(query: str) -> dict:
    sql = clean_sql(query)
    upper_sql = sql.upper()

    if not sql:
        return {"valid": False, "reason": "The SQL query was empty"}

    if ";" in sql:
        return {
            "valid": False,
            "reason": "Multiple SQL statements are not permitted",
        }

    if not re.match(r"^SELECT\b", upper_sql):
        return {
            "valid": False,
            "reason": "Only SELECT queries are permitted",
        }

    blocked = [
        "DROP",
        "DELETE",
        "UPDATE",
        "INSERT",
        "ALTER",
        "TRUNCATE",
        "ATTACH",
        "PRAGMA",
        "CREATE",
        "REPLACE",
    ]

    for word in blocked:
        if re.search(rf"\b{word}\b", upper_sql):
            return {
                "valid": False,
                "reason": f"Blocked keyword: {word}",
            }

    return {"valid": True, "reason": "OK"}


def generate_sql(query: str) -> dict:
    prompt = f"""
{SCHEMA_CONTEXT}

User question:
{query}

Generate the simplest SQLite SELECT query that answers the question.
Return only the SQL query.
"""

    sql, input_tokens, output_tokens = ask_gemini(
        SQL_SYSTEM_INSTRUCTION,
        prompt,
    )

    return {
        "sql": clean_sql(sql),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def interpret_results(
    query: str,
    sql: str,
    columns: list[str],
    rows: list[tuple],
) -> tuple[str, int, int]:
    prompt = f"""
User question:
{query}

SQL query used:
{sql}

Columns:
{columns}

Results:
{rows[:20]}

Provide a clear, concise interpretation of these results.
"""

    return ask_gemini(
        INTERPRETATION_SYSTEM_INSTRUCTION,
        prompt,
    )


def run(query: str) -> dict:
    sql_result = generate_sql(query)
    sql = sql_result["sql"]
    validation = validate_sql(sql)

    if not validation["valid"]:
        return {
            "answer": f"Query blocked: {validation['reason']}",
            "sql": sql,
            "rows": [],
            "validation": "FAILED",
            "input_tokens": sql_result["input_tokens"],
            "output_tokens": sql_result["output_tokens"],
        }

    try:
        connection = sqlite3.connect("./data/database.sqlite")
        cursor = connection.cursor()
        cursor.execute(sql)

        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]

        connection.close()

        answer, interpretation_input, interpretation_output = (
            interpret_results(query, sql, columns, rows)
        )

        return {
            "answer": answer,
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "validation": "PASSED",
            "input_tokens": (
                sql_result["input_tokens"] + interpretation_input
            ),
            "output_tokens": (
                sql_result["output_tokens"] + interpretation_output
            ),
        }

    except Exception as error:
        return {
            "answer": f"Query execution failed: {error}",
            "sql": sql,
            "rows": [],
            "validation": "ERROR",
            "input_tokens": sql_result["input_tokens"],
            "output_tokens": sql_result["output_tokens"],
        }


if __name__ == "__main__":
    question = input("Ask a question about the database: ").strip()
    result = run(question)

    print("\nGENERATED SQL")
    print(result["sql"])

    print("\nVALIDATION")
    print(result["validation"])

    print("\nANSWER")
    print(result["answer"])

    print(f"\nInput tokens: {result['input_tokens']}")
    print(f"Output tokens: {result['output_tokens']}")
