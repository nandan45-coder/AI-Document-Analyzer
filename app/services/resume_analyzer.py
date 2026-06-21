import json

from app.database import SessionLocal
from app.models.chunk import Chunk

from app.services.gemini_service import model


def analyze_resume(document_id):

    db = SessionLocal()

    chunks = (
        db.query(Chunk)
        .filter(
            Chunk.document_id == document_id
        )
        .all()
    )

    db.close()

    if not chunks:
        return None

    context = "\n".join(
        chunk.chunk_text
        for chunk in chunks
    )

    prompt = f"""
Analyze the following resume.

Return ONLY valid JSON.

Format:

{{
    "candidate_name": "",
    "education": [],
    "cgpa": "",
    "skills": [],
    "projects": [],
    "internships": [],
    "strengths": [],
    "weaknesses": [],
    "improvement_suggestions": []
}}

Rules:

1. Return JSON only.
2. No markdown.
3. No explanation.
4. No extra text.
5. Use ONLY information present in the resume.
6. If something is not available, return an empty string or empty list.

Resume:

{context}
"""

    response = model.generate_content(
        prompt
    )

    cleaned_response = (
        response.text
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    try:
        return json.loads(
            cleaned_response
        )

    except Exception:

        return {
            "error":
            "JSON Parsing Failed",
            "raw_output":
            response.text
        }