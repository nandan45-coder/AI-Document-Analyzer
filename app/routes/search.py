from fastapi import APIRouter

from app.services.chroma_service import (
    search_documents
)

router = APIRouter()

@router.get("/search")
def search(query: str):

    results = search_documents(
        query=query,
        top_k=3
    )

    documents = results["documents"][0]

    return {
        "query": query,
        "top_matches": documents
    }