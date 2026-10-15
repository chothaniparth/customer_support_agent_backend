from langchain_core.documents import Document
from app.ai.retriever import vector_store
from pathlib import Path
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.ai.retriever import vector_store

DOCUMENT_DIR = Path("Documents")

splitter = RecursiveCharacterTextSplitter(
    chunk_size = 1000,
    chunk_overlap = 150
)

def load_documents():
    documents = []

    for path in DOCUMENT_DIR.rglob("*"):
        if not path.is_file():
            continue

        print(f"Processing: {path}")

        if path.suffix.lower() == ".pdf":
            loader = PyPDFLoader(str(path))
        elif path.suffix.lower() == ".txt":
            loader = TextLoader(str(path), encoding="utf-8")
        else:
            continue

        loaded = loader.load()

        for doc in loaded:
            doc.metadata["source"] = path.name

        documents.extend(loaded)

    return documents

def ingest_documents():
    documents = load_documents()

    if not documents:
        print("No PDF or TXT documents found.")
        return
    
    chunks = splitter.split_documents(documents)

    vector_store.add_documents(chunks)

    print(f"Loaded {len(documents)} document pages/files.")
    print(f"Indexed {len(chunks)} chunks in Pinecone.")
    
if __name__ == "__main__":
    ingest_documents()