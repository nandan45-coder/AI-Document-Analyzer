from app.database import SessionLocal

from app.models.chunk import Chunk

from app.services.gemini_service import (
    generate_summary
)


def summarize_document(
    document_id
):

    db = SessionLocal()

    chunks = db.query(
        Chunk
    ).filter(
        Chunk.document_id == document_id
    ).all()

    db.close()

    if not chunks:
        return None

    full_text = "\n".join(
        chunk.chunk_text
        for chunk in chunks
    )

    summary = generate_summary(
        full_text
    )

    return summary