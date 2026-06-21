from sqlalchemy import Column, Integer, String, Text
from app.database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    
    filename = Column(String)
    filetype = Column(String)
    filepath = Column(String)
    filesize = Column(String)

    extracted_text = Column(Text)