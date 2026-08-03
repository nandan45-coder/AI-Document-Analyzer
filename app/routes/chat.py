from typing import Optional
from fastapi import APIRouter, Query

from app.services.chroma_service import (
    search_documents
)

from app.services.gemini_service import (
    generate_answer
)

router = APIRouter()


@router.get("/chat")
def chat(
    question: str = Query(..., description="User question"),
    doc_id: Optional[int] = Query(None, description="Document ID to filter chat context"),
    document_id: Optional[int] = Query(None, description="Alternative parameter for Document ID"),
):
    target_doc_id = doc_id if doc_id is not None else document_id

    results = search_documents(
        query=question,
        top_k=3,
        doc_id=target_doc_id
    )

    documents = results.get("documents", [])

    if not documents or not documents[0]:
        response = {
            "question": question,
            "answer": "No relevant information found in the document."
        }
        if target_doc_id is not None:
            response["doc_id"] = target_doc_id
        return response

    retrieved_chunks = documents[0]

    context = "\n\n".join(
        retrieved_chunks
    )

    print("\n========== RETRIEVED CONTEXT ==========")
    print(context)
    print("=======================================\n")

    answer = generate_answer(
        question=question,
        context=context
    )

    response = {
        "question": question,
        "answer": answer
    }

    if target_doc_id is not None:
        response["doc_id"] = target_doc_id

    return response