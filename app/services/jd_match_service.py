import json

from app.database import SessionLocal
from app.models.chunk import Chunk
from app.services.gemini_service import model


def match_resume_with_jd(document_id: int, job_description: str):

    db = SessionLocal()

    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_id == document_id)
        .all()
    )

    db.close()

    if not chunks:
        return {
            "error": "No document chunks found."
        }

    resume_text = "\n".join(
        chunk.chunk_text
        for chunk in chunks
    )

    prompt = f"""
You are an expert ATS Resume Evaluator.

Compare the following Resume with the Job Description.

Return ONLY valid JSON.

Format:

{{
    "match_score": 0,

    "matched_skills": [],

    "missing_skills": [],

    "strengths": [],

    "weaknesses": [],

    "recommendations": [],

    "interview_probability": ""
}}

Rules:

1. Return JSON only.
2. Do not use markdown.
3. Do not explain.
4. Score should be between 0-100.
5. Use only information from Resume and Job Description.

Resume:

{resume_text}

Job Description:

{job_description}
"""

    response = model.generate_content(prompt)

    cleaned = (
        response.text
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    try:
        return json.loads(cleaned)

    except Exception:

        return {
            "error": "JSON Parsing Failed",
            "raw_output": response.text
        }