from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.chunk import Chunk
from app.models.embedding import Embedding

from app.services.chroma_service import (
    store_embedding
)

import json

router = APIRouter()


@router.post("/chroma/{document_id}")
def store_in_chroma(
    document_id: int,
    db: Session = Depends(get_db)
):

    chunks = (
        db.query(Chunk)
        .filter(
            Chunk.document_id == document_id
        )
        .all()
    )

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="Chunks not found"
        )

    total = 0

    for chunk in chunks:

        embedding = (
            db.query(Embedding)
            .filter(
                Embedding.chunk_id == chunk.id
            )
            .first()
        )

        if embedding:

            vector = json.loads(
                embedding.embedding_vector
            )

            store_embedding(
                chunk.id,
                document_id,
                chunk.chunk_text,
                vector
            )

            total += 1

    return {
        "document_id": document_id,
        "stored_vectors": total,
        "status": "stored"
    }