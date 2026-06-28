import json

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.chunk import Chunk
from app.data.roles import ROLE_SKILLS

from app.services.gemini_service import model


class InterviewPreparationService:

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

        resume_text: str,

        selected_role: str,

        difficulty: str,

        total_questions: int

    ):

        role_data = ROLE_SKILLS.get(selected_role)

        if role_data is None:

            raise Exception("Invalid Job Role")

        prompt = f"""
You are an Expert Technical Interviewer,
Senior HR Manager,
Hiring Manager,
Software Architect,
and Career Coach.

The candidate uploaded the following resume.

=========================
RESUME
=========================

{resume_text}

=========================
TARGET ROLE
=========================

{selected_role}

=========================
ROLE DESCRIPTION
=========================

{role_data["description"]}

=========================
REQUIRED SKILLS
=========================

{", ".join(role_data["skills"])}

=========================
INTERVIEW LEVEL
=========================

{difficulty}

=========================
TASK
=========================

Generate a COMPLETE interview preparation guide.

The interview questions MUST be personalized
according to

1 Resume

2 Projects

3 Internship

4 Skills

5 Selected Job Role

6 Difficulty Level

Generate exactly {total_questions} questions.

Divide them into the following categories.

1 HR Questions

2 Resume Questions

3 Technical Questions

4 Project Questions

5 Coding Questions

6 Scenario Based Questions

For EVERY question provide

• Question

• Expected Answer

• Interview Tip

• Difficulty

• Important Topics

Finally provide

1 Interview Readiness Score

2 Top Strengths

3 Weak Areas

4 Missing Skills

5 Study Plan

6 Estimated Preparation Time

Return ONLY JSON.

Required Format

{{
    "target_role":"",

    "difficulty":"",

    "overall_readiness":0,

    "estimated_preparation_days":0,

    "top_strengths":[],

    "weak_areas":[],

    "missing_skills":[],

    "study_plan":[],

    "categories":{{

        "hr_questions":[

            {{
                "question":"",
                "expected_answer":"",
                "tip":"",
                "difficulty":"",
                "topics":[]
            }}

        ],

        "resume_questions":[

            {{

                "question":"",
                "expected_answer":"",
                "tip":"",
                "difficulty":"",
                "topics":[]

            }}

        ],

        "technical_questions":[

            {{

                "question":"",
                "expected_answer":"",
                "tip":"",
                "difficulty":"",
                "topics":[]

            }}

        ],

        "project_questions":[

            {{

                "question":"",
                "expected_answer":"",
                "tip":"",
                "difficulty":"",
                "topics":[]

            }}

        ],

        "coding_questions":[

            {{

                "question":"",
                "expected_answer":"",
                "tip":"",
                "difficulty":"",
                "topics":[]

            }}

        ],

        "scenario_questions":[

            {{

                "question":"",
                "expected_answer":"",
                "tip":"",
                "difficulty":"",
                "topics":[]

            }}

        ]

    }}

}}
"""

        return prompt
    
    def generate_interview_guide(
        self,
        document_id: int,
        selected_role: str,
        difficulty: str,
        total_questions: int
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

            if selected_role not in ROLE_SKILLS:

                return {
                    "success": False,
                    "message": "Invalid Job Role."
                }

            prompt = self.build_prompt(
                resume_text=resume_text,
                selected_role=selected_role,
                difficulty=difficulty,
                total_questions=total_questions
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

                interview_data = json.loads(output)

            except Exception:

                return {

                    "success": False,

                    "message": "Unable to parse Gemini JSON.",

                    "raw_output": output

                }

            return {

                "success": True,

                "document_id": document_id,

                "selected_role": selected_role,

                "difficulty": difficulty,

                "interview_guide": interview_data

            }

        except Exception as e:

            return {

                "success": False,

                "error": str(e)

            }

        finally:

            self.db.close()


interview_service = InterviewPreparationService()