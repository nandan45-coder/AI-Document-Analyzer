from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.document import Document

import os
import shutil

router = APIRouter()

UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt"]

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type"
        )

    file_path = os.path.join(
        UPLOAD_DIR,
        file.filename
    )

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    document = Document(
        filename=file.filename,
        filetype=ext,
        filepath=file_path,
        filesize=str(os.path.getsize(file_path))
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return {
        "document_id": document.id,
        "filename": document.filename,
        "path": document.filepath
    }