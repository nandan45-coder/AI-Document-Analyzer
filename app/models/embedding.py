from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import ForeignKey

from app.database import Base


class Embedding(Base):

    __tablename__ = "embeddings"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    chunk_id = Column(
        Integer,
        ForeignKey("chunks.id")
    )

    embedding_vector = Column(
        Text
    )