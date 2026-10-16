from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

from app.core.config import settings

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=settings.OPENAI_API_KEY
)

pc = Pinecone(api_key= settings.PINECONE_API_KEY)

index = pc.Index(settings.PINECONE_INDEX_NAME)

vector_store = PineconeVectorStore(
    index = index,
    embedding = embeddings,
)

retriever = vector_store.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={
        "k": 3,
        "score_threshold": 0.5,
    },
)

def get_user_retriever(user_id: str):
    # Return docs that belong to this user OR are public (batch-ingested store docs).
    return vector_store.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={
            "k": 3,
            "score_threshold": 0.5,
            "filter": {
                "user_id": {"$in": [user_id, "public"]}
            },
        },
    )


def debug_retrieval(question: str, user_id: str):
    results = vector_store.similarity_search_with_relevance_scores(
        question,
        k=5,
        filter={"user_id": {"$eq": user_id}},
    )

    if not results:
        print("No matching documents found.")
        return

    for i, (doc, score) in enumerate(results, start=1):
        print(f"\nResult {i} | Relevance: {score:.3f}")
        print(f"Source: {doc.metadata.get('source', 'Unknown')}")
        print(f"Content: {doc.page_content[:500]}")