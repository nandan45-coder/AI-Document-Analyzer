import json

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.chunk import Chunk

from app.services.gemini_service import model


class ResumeImproverService:

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
You are an expert Resume Writer,
ATS Optimization Expert,
HR Recruiter,
Career Coach,
and Technical Hiring Manager.

Your task is to improve the uploaded resume professionally.

Resume:

{resume_text}

Perform ALL of the following improvements.

1.
Write a professional summary.

2.
Improve all technical skills.

3.
Improve project descriptions.

4.
Improve internship descriptions.

5.
Improve certifications section.

6.
Improve achievements.

7.
Improve grammar.

8.
Improve formatting.

9.
Add ATS keywords.

10.
Suggest additional skills.

11.
Suggest certifications.

12.
Suggest projects.

13.
Suggest interview preparation tips.

14.
Estimate ATS Score Before Improvement.

15.
Estimate ATS Score After Improvement.

Return ONLY JSON.

Format:

{{
    "professional_summary":"",

    "technical_skills":{{

        "programming_languages":[],

        "frameworks":[],

        "databases":[],

        "tools":[],

        "ai_ml":[]
    }},

    "improved_projects":[

        {{

            "title":"",

            "description":""

        }}

    ],

    "improved_internships":[

        {{

            "company":"",

            "description":""

        }}

    ],

    "improved_certifications":[],

    "improved_achievements":[],

    "ats_keywords_added":[],

    "additional_skills":[],

    "recommended_certifications":[],

    "recommended_projects":[],

    "grammar_improvements":[],

    "interview_tips":[],

    "ats_score_before":0,

    "ats_score_after":0
}}
"""

        return prompt
        
    def improve_resume(
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

            # Remove Markdown if Gemini returns it
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

                improved_resume = json.loads(
                    output
                )

            except Exception:

                return {

                    "success": False,

                    "message": "Unable to parse Gemini JSON response.",

                    "raw_output": output

                }

            return {

                "success": True,

                "document_id": document_id,

                "resume_improvement": improved_resume

            }

        except Exception as e:

            return {

                "success": False,

                "error": str(e)

            }

        finally:

            self.db.close()


resume_improver_service = ResumeImproverService()