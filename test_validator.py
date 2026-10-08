from validation.validator import (
    validate_qualitative,
    validate_quantitative,
)

chunks = [
    {
        "source": "remote_work_policy.txt",
        "chunk": 0,
        "content": "Employees need manager approval for remote work.",
    },
    {
        "source": "benefits_policy.txt",
        "chunk": 1,
        "content": "Eligible employees receive health benefits.",
    },
]

tests = [
    (
        "Grounded qualitative response",
        validate_qualitative(
            "Employees need manager approval for remote work [Source 1].",
            chunks,
        ),
    ),
    (
        "Ungrounded qualitative response",
        validate_qualitative(
            "The company has offices in 50 countries.",
            chunks,
        ),
    ),
    (
        "Correct qualitative refusal",
        validate_qualitative(
            "I cannot find this information in the provided documents.",
            chunks,
        ),
    ),
    (
        "Blocked quantitative response",
        validate_quantitative(
            answer="Query blocked: Only SELECT queries are permitted.",
            sql="DELETE FROM sales",
            validation_status="FAILED",
        ),
    ),
]

for test_name, result in tests:
    print(f"\n{test_name}")
    print(result)
