import logging
import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.schemas.govt_document import GovtDocumentResponse
from app.services.govt_report_service import govt_report_service

logger = logging.getLogger("govt_document_intelligence")

router = APIRouter(
    prefix="/govt",
    tags=["Government Document Intelligence"],
)

UPLOAD_FOLDER = "temp_govt_documents"
Path(UPLOAD_FOLDER).mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg"]

# 15 MB - generous for a scanned certificate while still preventing abuse.
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024


# =====================================================
# Analyze Government Document
# =====================================================

@router.post("/analyze", response_model=GovtDocumentResponse)
async def analyze_document(file: UploadFile = File(...)):

    save_path = None

    try:
        extension = os.path.splitext(file.filename)[1].lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format.",
            )

        # Unique filename prevents collisions between concurrent uploads
        # that happen to share the same original filename.
        unique_name = f"{uuid.uuid4().hex}{extension}"
        save_path = os.path.join(UPLOAD_FOLDER, unique_name)

        size_written = 0

        with open(save_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                size_written += len(chunk)

                if size_written > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail="File exceeds maximum allowed size of 15 MB.",
                    )

                buffer.write(chunk)

        if size_written == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # OCR/CV work is CPU-bound and blocking - run it off the event loop
        # so one heavy document doesn't stall other requests.
        result = await run_in_threadpool(
            govt_report_service.generate_report, save_path
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Unhandled error while analyzing document.")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if save_path and os.path.exists(save_path):
            try:
                os.remove(save_path)
            except OSError:
                logger.warning("Failed to remove temp file %s", save_path)


# =====================================================
# Health Check
# =====================================================

@router.get("/health")
def health():
    return {
        "success": True,
        "module": "Government Document Intelligence",
        "status": "Running",
    }