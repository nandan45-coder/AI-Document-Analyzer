from fastapi import APIRouter

from app.services.career_service import career_service

router = APIRouter(
    prefix="/career",
    tags=["Career Recommendation"]
)


@router.get("/{document_id}")
def recommend_career(document_id: int):

    return career_service.recommend_career(document_id)