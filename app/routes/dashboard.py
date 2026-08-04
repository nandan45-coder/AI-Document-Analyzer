from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_optional_current_user
from app.models.user import User
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import dashboard_service


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


# =====================================================
# Dashboard
#
# Single endpoint returning welcome info, statistics, and quick-access
# shortcuts together. Performs NO AI processing - only reads data already
# stored in the database (returning 0 for any statistic whose source
# table doesn't exist yet). The authenticated user always comes from the
# JWT via get_optional_current_user; there is no way to request another user's
# dashboard.
# =====================================================

@router.get(
    "",
    response_model=DashboardResponse,
)
def get_dashboard(
    current_user: User = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    return dashboard_service.get_dashboard(db, current_user)