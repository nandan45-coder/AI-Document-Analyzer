from fastapi import APIRouter

from app.services.chroma_service import (
    search_documents
)

from app.services.gemini_service import (
    generate_answer
)

router = APIRouter()


@router.get("/chat")
def chat(question: str):

    results = search_documents(
        query=question,
        top_k=1
    )

    documents = results.get("documents", [])

    if not documents or not documents[0]:
        return {
            "question": question,
            "answer": "No relevant information found in the document."
        }

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

    return {
        "question": question,
        "answer": answer
    }