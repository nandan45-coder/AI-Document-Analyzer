import logging
from fastapi import FastAPI

from app.database import engine, Base

# Import Models
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.embedding import Embedding

# Import Routes
from app.routes.upload import router
from app.routes.process import router as process_router
from app.routes.chunk import router as chunk_router
from app.routes import ats
from app.routes.jd_match import router as jd_match_router
from app.routes.embedding import (
    router as embedding_router
)
from app.routes.chroma import (
    router as chroma_router
)
from app.routes.search import (
    router as search_router
)
from app.routes.chat import (
    router as chat_router
)
from app.routes.summary import (
    router as summary_router
)
from app.routes.resume import (
    router as resume_router
)
from app.routes.career import (
    router as career_router
)
from app.routes.resume_improver import (
    router as resume_improver_router
)
from app.routes.score_dashboard import (
    router as score_dashboard_router
)
from app.routes.interview import (
    router as interview_router
)
from app.routes.govt_document import (
    router as govt_document_router
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# Create Database Tables
Base.metadata.create_all(bind=engine)

# Create FastAPI App
app = FastAPI(
    title="AI Document Analyzer",
    description="AI-powered Document Analysis System",
    version="1.0.0"
)

# Register Routes
app.include_router(router)
app.include_router(process_router)
app.include_router(chunk_router)
app.include_router(embedding_router)
app.include_router(chroma_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(summary_router)
app.include_router(resume_router)
app.include_router(ats.router)
app.include_router(jd_match_router)
app.include_router(career_router)
app.include_router(resume_improver_router)
app.include_router(score_dashboard_router)
app.include_router(interview_router)
app.include_router(govt_document_router)



@app.get("/")
def home():
    return {
        "message": "AI Document Analyzer Running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "application": "AI Document Analyzer"
    }

