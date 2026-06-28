import json

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.chunk import Chunk

from app.services.gemini_service import model


class ResumeScoreDashboardService:

    def __init__(self):

        self.db: Session = SessionLocal()

    def get_resume_text(
        self,
        document_id: int
    ):

        chunks = (

            self.db.query(Chunk)

            .filter(
                Chunk.document_id == document_id
            )

            .all()

        )

        if not chunks:

            return None

        resume = "\n".join(

            chunk.chunk_text

            for chunk in chunks

        )

        return resume


    def build_prompt(
        self,
        resume_text: str
    ):

        prompt = f"""
You are an Expert ATS Recruiter,
Senior HR Manager,
Resume Reviewer,
Career Coach,
and Technical Hiring Manager.

Evaluate the following resume.

Resume:

{resume_text}

Score the resume in the following categories.

1. Overall Resume Score

2. ATS Compatibility

3. Technical Skills

4. Projects

5. Internship

6. Education

7. Certifications

8. Achievements

9. Grammar

10. Formatting

11. Communication

12. Leadership

13. Problem Solving

14. Career Readiness

Also provide

Top Strengths

Top Weaknesses

Highest Priority Improvements

Overall Rating

Career Advice

Interview Readiness

Return ONLY JSON.

Format

{{
    "overall_resume_score":0,

    "ats_score":0,

    "technical_skills_score":0,

    "projects_score":0,

    "internship_score":0,

    "education_score":0,

    "certification_score":0,

    "achievement_score":0,

    "grammar_score":0,

    "formatting_score":0,

    "communication_score":0,

    "leadership_score":0,

    "problem_solving_score":0,

    "career_readiness_score":0,

    "overall_rating":"",

    "interview_readiness":"",

    "top_strengths":[],

    "top_weaknesses":[],

    "highest_priority_improvements":[],

    "career_advice":[]

}}
"""

        return prompt
    
    def generate_dashboard(
        self,
        document_id: int
    ):

        try:

            resume_text = self.get_resume_text(
                document_id
            )

            if resume_text is None:

                return {
                    "success": False,
                    "message": "Resume not found."
                }

            prompt = self.build_prompt(
                resume_text
            )

            response = model.generate_content(
                prompt
            )

            output = response.text.strip()

            # Remove markdown formatting if Gemini returns it
            if output.startswith("```json"):

                output = (
                    output
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
                )

            elif output.startswith("```"):

                output = (
                    output
                    .replace("```", "")
                    .strip()
                )

            try:

                dashboard = json.loads(output)

            except Exception:

                return {

                    "success": False,

                    "message": "Unable to parse Gemini response.",

                    "raw_output": output

                }

            return {

                "success": True,

                "document_id": document_id,

                "dashboard": dashboard

            }

        except Exception as e:

            return {

                "success": False,

                "error": str(e)

            }

        finally:

            self.db.close()


resume_score_dashboard_service = ResumeScoreDashboardService()