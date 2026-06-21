from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.chunk import Chunk
from app.models.embedding import Embedding

from app.services.embedding_service import (
    generate_embedding
)

import json


router = APIRouter()


@router.post("/embedding/{document_id}")
def create_embeddings(
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

    old_embeddings = (
        db.query(Embedding)
        .all()
    )

    for emb in old_embeddings:
        db.delete(emb)

    db.commit()

    for chunk in chunks:

        vector = generate_embedding(
            chunk.chunk_text
        )

        embedding = Embedding(
            chunk_id=chunk.id,
            embedding_vector=json.dumps(
                vector
            )
        )

        db.add(embedding)

    db.commit()

    return {
        "document_id": document_id,
        "total_embeddings": len(chunks),
        "status": "generated"
    }