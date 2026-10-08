def validate_qualitative(answer: str, chunks: list[dict]) -> dict:
    sources_cited = []

    for index, chunk in enumerate(chunks, start=1):
        if f"Source {index}" in answer:
            sources_cited.append(chunk["source"])

    grounded = len(sources_cited) > 0
    refused = "cannot find" in answer.lower()
    flagged = not grounded and not refused

    return {
        "is_grounded": grounded,
        "refused_to_answer": refused,
        "sources_cited": sources_cited,
        "flag": flagged,
        "warning": (
            "Response may not be grounded in source documents"
            if flagged
            else None
        ),
    }


def validate_quantitative(
    answer: str,
    sql: str,
    validation_status: str,
) -> dict:
    sql_validated = validation_status == "PASSED"
    sql_blocked = validation_status == "FAILED"
    execution_error = validation_status == "ERROR"
    flagged = not sql_validated

    return {
        "sql_validated": sql_validated,
        "sql_blocked": sql_blocked,
        "execution_error": execution_error,
        "flag": flagged,
        "warning": (
            f"SQL validation status: {validation_status}"
            if flagged
            else None
        ),
    }
