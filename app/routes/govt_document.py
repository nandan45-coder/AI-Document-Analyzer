import os
import shutil
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    HTTPException
)

from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.govt_document_history import GovernmentDocumentHistory
from app.models.user import User

from app.schemas.govt_document import (
    GovtDocumentResponse
)

from app.services.govt_report_service import (
    govt_report_service
)


router = APIRouter(

    prefix="/govt",

    tags=["Government Document Intelligence"]

)


UPLOAD_FOLDER = "temp_govt_documents"

Path(UPLOAD_FOLDER).mkdir(

    exist_ok=True

)


# =====================================================
# Analyze Government Document
# =====================================================

@router.post(

    "/analyze",

    response_model=GovtDocumentResponse

)

async def analyze_document(

    file: UploadFile = File(...),

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db),

):

    try:

        extension = os.path.splitext(

            file.filename

        )[1].lower()

        if extension not in [

            ".pdf",

            ".png",

            ".jpg",

            ".jpeg"

        ]:

            raise HTTPException(

                status_code=400,

                detail="Unsupported file format."

            )

        save_path = os.path.join(

            UPLOAD_FOLDER,

            file.filename

        )

        with open(

            save_path,

            "wb"

        ) as buffer:

            shutil.copyfileobj(

                file.file,

                buffer

            )

        result = govt_report_service.generate_report(

            save_path

        )

        os.remove(

            save_path

        )

        if not result["success"]:

            raise HTTPException(

                status_code=500,

                detail=result["error"]

            )

        # Record this verification in the authenticated user's history -
        # this is what powers the Dashboard's "Total Government Documents"
        # statistic. Recorded only after a confirmed success above, so a
        # failed/errored analysis never gets counted.
        history_entry = GovernmentDocumentHistory(

            user_id=current_user.id,

            filename=file.filename,

            document_type=result.get("document_type"),

            verification_status=(
                result.get("verification", {}).get("verification_status")
            ),

            ready_for_submission=(
                result.get("verification", {}).get("ready_for_submission", False)
            ),

            overall_confidence=(
                result.get("overall_confidence", {}).get("overall_confidence")
            ),

        )

        db.add(history_entry)
        db.commit()

        return result

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=str(e)

        )


# =====================================================
# Health Check
# =====================================================

@router.get("/health")

def health():

    return {

        "success": True,

        "module": "Government Document Intelligence",

        "status": "Running"

    }