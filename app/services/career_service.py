import json

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.chunk import Chunk
from app.data.roles import ROLE_SKILLS

from app.services.gemini_service import model


class CareerRecommendationService:

    def __init__(self):

        self.db: Session = SessionLocal()

    def get_resume_text(self, document_id: int):

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

    def calculate_role_scores(self, resume_text):

        resume = resume_text.lower()

        results = []

        for role_name, role_data in ROLE_SKILLS.items():

            required_skills = role_data["skills"]

            matched = []

            missing = []

            score = 0

            for skill in required_skills:

                if skill.lower() in resume:

                    matched.append(skill)

                    score += 1

                else:

                    missing.append(skill)

            percentage = round(

                (score / len(required_skills)) * 100,

                2

            )

            results.append(

                {

                    "role": role_name,

                    "match_score": percentage,

                    "matched_skills": matched,

                    "missing_skills": missing,

                    "career_level": role_data["career_level"],

                    "salary_range": role_data["salary_range"],

                    "description": role_data["description"],

                    "tools": role_data["tools"]

                }

            )

        results.sort(

            key=lambda x: x["match_score"],

            reverse=True

        )

        return results

    def get_top_roles(

            self,

            role_scores,

            top_n=5

    ):

        return role_scores[:top_n]

    def build_prompt(

            self,

            resume_text,

            top_roles

    ):

        prompt = f"""
You are an Expert Career Guidance AI.

A candidate uploaded the following resume.

Resume:

{resume_text}

Based on the following Top Career Matches:

{json.dumps(top_roles, indent=4)}

Generate career recommendations.

Return ONLY JSON.

Required Format:

{{
    "career_recommendations":[
        {{
            "role":"",
            "match_score":0,
            "why_this_role":"",
            "career_level":"",
            "salary_range":"",
            "matched_skills":[],
            "missing_skills":[],
            "learning_roadmap":[
                ""
            ],
            "interview_tips":[
                ""
            ]
        }}
    ]
}}
"""

        return prompt

    def recommend_career(self, document_id: int):
        try:

            resume_text = self.get_resume_text(document_id)

            if resume_text is None:

                return {
                    "success": False,
                    "message": "Resume not found."
                }

            role_scores = self.calculate_role_scores(
                resume_text
            )

            top_roles = self.get_top_roles(
                role_scores,
                top_n=5
            )

            prompt = self.build_prompt(
                resume_text,
                top_roles
            )

            response = model.generate_content(prompt)

            raw_response = response.text.strip()

            if raw_response.startswith("```json"):

                raw_response = (
                    raw_response
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
                )

            elif raw_response.startswith("```"):

                raw_response = (
                    raw_response
                    .replace("```", "")
                    .strip()
                )

            try:

                gemini_result = json.loads(
                    raw_response
                )

            except Exception:

                gemini_result = {
                    "career_recommendations": top_roles
                }

            return {

                "success": True,

                "total_roles_checked": len(
                    ROLE_SKILLS
                ),

                "top_matching_roles": top_roles,

                "ai_career_guidance": gemini_result

            }

        except Exception as e:

            return {

                "success": False,

                "error": str(e)

            }

        finally:

            self.db.close()


career_service = CareerRecommendationService()