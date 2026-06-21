from sqlalchemy import Column, Integer, Text, ForeignKey
from app.database import Base


class Chunk(Base):

    __tablename__ = "chunks"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.id")
    )

    chunk_index = Column(
        Integer
    )

    chunk_text = Column(
        Text
    )