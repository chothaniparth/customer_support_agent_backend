
from app.ai.retriever import vector_store
from app.ai.graph import generate_graph_response

USER_ID = "df15d99b-09e1-4b72-8e86-5071e9ddfde9"

TEST_CASES = [
    {
        "question": "What is the refund period?",
        "expected_source": "Nestora_Refund_and_Return_Policy.pdf",
        "expected_facts": ["30 days"],
    },
    {
        "question": "What condition must a product meet to qualify for a refund?",
        "expected_source": "Nestora_Refund_and_Return_Policy.pdf",
        "expected_facts": ["unused", "original packaging"],
    },
    {
        "question": "What are the specifications of the NK-500 kettle?",
        "expected_source": "Nestora_Brew_Smart_Kettle_NK-500_Manual.pdf",
        "expected_facts": [],  # Add verified facts from your manual
    },
]

def evaluate():
    retrieval_passes = 0
    answer_checks_pass = 0

    for i, case in enumerate(TEST_CASES, start=1):
        question = case["question"]

        results = vector_store.similarity_search_with_relevance_scores(
            question,
            k=3,
            filter={"user_id": {"$eq": USER_ID}},
        )

        sources = [
            doc.metadata.get("source", "")
            for doc, score in results
        ]

        retrieval_ok = any(
            case["expected_source"].lower() in source.lower()
            for source in sources
        )

        if retrieval_ok:
            retrieval_passes += 1

        answer = generate_graph_response(
            [{"role": "user", "content": question}],
            USER_ID,
        )

        answer_lower = answer.lower()
        expected_facts = case["expected_facts"]

        # A simple keyword check, not a full semantic evaluation.
        facts_ok = (
            all(fact.lower() in answer_lower for fact in expected_facts)
            if expected_facts
            else None
        )

        if facts_ok is True:
            answer_checks_pass += 1

        print(f"\n{'=' * 55}")
        print(f"Test {i}: {question}")
        print(f"Retrieved sources: {sources}")
        print(f"Expected source found: {retrieval_ok}")
        print(f"Answer: {answer}")
        print(f"Expected facts found: {facts_ok}")

    total = len(TEST_CASES)

    print(f"\n{'=' * 55}")
    print(f"Retrieval source hit rate: {retrieval_passes}/{total}")
    print(
        "Keyword checks passed: "
        f"{answer_checks_pass}/{sum(bool(c['expected_facts']) for c in TEST_CASES)}"
    )

if __name__ == "__main__":
    evaluate()