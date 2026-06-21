from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Document
from app.services.document_processor import extract_text

router = APIRouter()


@router.post("/process/{document_id}")
def process_document(
    document_id: int,
    db: Session = Depends(get_db)
):

    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    try:
        extracted_text = extract_text(
            document.filepath
        )

        document.extracted_text = extracted_text

        db.commit()

        return {
            "document_id": document.id,
            "status": "processed",
            "characters": len(extracted_text),
            "preview": extracted_text[:500]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )