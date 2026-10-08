from agents.manager import print_result, run


def main():
    print("Spoonful Enterprise RAG System")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        query = input("Ask a question: ").strip()

        if query.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break

        if not query:
            continue

        result = run(query)
        print_result(result)


if __name__ == "__main__":
    main()
