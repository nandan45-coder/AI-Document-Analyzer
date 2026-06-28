from typing import Dict

from pydantic import BaseModel


class ScoreDashboardResponse(BaseModel):

    success: bool

    document_id: int

    dashboard: Dict