from typing import Optional
from fastapi import APIRouter, Query

from app.services.chroma_service import (
    search_documents
)

router = APIRouter()


@router.get("/search")
def search(
    doc_id: Optional[int] = Query(None, description="Document ID to filter search results"),
    query: str = Query(..., description="Search query string"),
    document_id: Optional[int] = Query(None, description="Alternative parameter name for Document ID"),
):
    target_doc_id = doc_id if doc_id is not None else document_id

    results = search_documents(
        query=query,
        top_k=3,
        doc_id=target_doc_id
    )

    documents = results["documents"][0] if results and "documents" in results and results["documents"] else []

    response = {
        "query": query,
        "top_matches": documents
    }

    if target_doc_id is not None:
        response["doc_id"] = target_doc_id

    return response