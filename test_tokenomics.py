from tokenomics.logger import log


entry = log(
    query="Show me monthly revenue trends",
    agent="quantitative",
    input_tokens=100,
    output_tokens=50,
)

print(entry)
