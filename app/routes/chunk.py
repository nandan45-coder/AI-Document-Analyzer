from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.document import Document
from app.models.chunk import Chunk

from app.services.chunking_service import (
    create_chunks
)

router = APIRouter()


@router.post("/chunk/{document_id}")
def chunk_document(
    document_id: int,
    db: Session = Depends(get_db)
):

    document = (
        db.query(Document)
        .filter(
            Document.id == document_id
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    if not document.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="Document not processed yet"
        )

    old_chunks = (
        db.query(Chunk)
        .filter(
            Chunk.document_id == document.id
        )
        .all()
    )

    for chunk in old_chunks:
        db.delete(chunk)

    db.commit()

    chunks = create_chunks(
        document.extracted_text
    )

    for index, chunk_text in enumerate(chunks):

        chunk = Chunk(
            document_id=document.id,
            chunk_index=index,
            chunk_text=chunk_text
        )

        db.add(chunk)

    db.commit()

    return {
        "document_id": document.id,
        "total_chunks": len(chunks),
        "status": "chunked"
    }