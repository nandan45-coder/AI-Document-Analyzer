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

