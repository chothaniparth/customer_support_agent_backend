
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pathlib import Path
from uuid import uuid4

from app.api.auth import get_current_user
from app.ai.ingest import splitter
from app.ai.retriever import vector_store
from langchain_community.document_loaders import PyPDFLoader, TextLoader

router = APIRouter(prefix="/api/documents", tags=["Documents"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    extension = Path(file.filename).suffix.lower()

    if extension not in {".pdf", ".txt"}:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and TXT files are supported",
        )

    file_id = str(uuid4())
    safe_filename = f"{file_id}{extension}"
    file_path = UPLOAD_DIR / safe_filename

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="File is empty")

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Maximum file size is 10 MB")

    file_path.write_bytes(content)

    try:
        if extension == ".pdf":
            loader = PyPDFLoader(str(file_path))
        else:
            loader = TextLoader(str(file_path), encoding="utf-8")

        documents = loader.load()

        if not documents:
            raise HTTPException(
                status_code=400,
                detail="No readable content found",
            )

        user_id = str(current_user.id)

        for doc in documents:
            doc.metadata["source"] = file.filename
            doc.metadata["user_id"] = user_id
            doc.metadata["document_id"] = file_id

        chunks = splitter.split_documents(documents)

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No text chunks could be created",
            )

        vector_store.add_documents(chunks)

        return {
            "message": "Document indexed successfully",
            "filename": file.filename,
            "document_id": file_id,
            "pages_or_sections": len(documents),
            "chunks_indexed": len(chunks),
        }

    except HTTPException as e:
        print(f"http error : {e}")
        raise
    except Exception as exc:
        print(f"exept error : {exc}")
        raise HTTPException(
            status_code=500,
            detail="Document processing or indexing failed",
        ) from exc
    finally:
        file_path.unlink(missing_ok=True)