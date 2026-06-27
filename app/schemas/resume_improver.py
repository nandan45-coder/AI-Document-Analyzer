from typing import List, Dict

from pydantic import BaseModel


class ResumeImprovementResponse(BaseModel):

    success: bool

    document_id: int

    resume_improvement: Dict