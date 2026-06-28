import json

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.chunk import Chunk
from app.models.interview_session import InterviewSession

from app.data.roles import ROLE_SKILLS
from app.services.gemini_service import model


class InterviewSessionService:

    def __init__(self):

        self.db: Session = SessionLocal()

    # ====================================================
    # Get Resume Text
    # ====================================================

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

        resume_text = "\n".join(

            chunk.chunk_text

            for chunk in chunks

        )

        return resume_text

    # ====================================================
    # Build Interview Prompt
    # ====================================================

    def build_prompt(

        self,

        resume_text: str,

        selected_role: str,

        difficulty: str,

        total_questions: int

    ):

        role_data = ROLE_SKILLS.get(selected_role)

        if role_data is None:

            raise Exception(
                "Invalid Job Role"
            )

        prompt = f"""
You are a Senior Technical Interviewer,
Hiring Manager,
HR Manager,
Career Coach
and Software Architect.

The following candidate uploaded a resume.

==================================
RESUME
==================================

{resume_text}

==================================
TARGET ROLE
==================================

{selected_role}

==================================
ROLE DESCRIPTION
==================================

{role_data["description"]}

==================================
REQUIRED SKILLS
==================================

{", ".join(role_data["skills"])}

==================================
INTERVIEW DIFFICULTY
==================================

{difficulty}

Generate EXACTLY {total_questions} interview questions.

Distribute them approximately as follows:

• HR Questions

• Resume Questions

• Technical Questions

• Project Questions

• Coding Questions

• Scenario Based Questions

For EVERY question generate

1 Question Number

2 Category

3 Question

4 Expected Answer

5 Difficulty

6 Important Topics

Return ONLY JSON.

Required JSON Format

{{
    "questions":[

        {{

            "question_number":1,

            "category":"Technical",

            "question":"",

            "expected_answer":"",

            "difficulty":"Intermediate",

            "topics":[
                ""
            ]

        }}

    ]
}}
"""

        return prompt
    
    # ====================================================
    # Create Interview Session
    # ====================================================

    def create_session(
        self,
        document_id: int,
        role: str,
        difficulty: str,
        total_questions: int
    ):

        try:

            # -----------------------------
            # Validate Role
            # -----------------------------

            if role not in ROLE_SKILLS:

                return None

            # -----------------------------
            # Get Resume
            # -----------------------------

            resume_text = self.get_resume_text(
                document_id
            )

            if resume_text is None:

                return None

            # -----------------------------
            # Generate Prompt
            # -----------------------------

            prompt = self.build_prompt(

                resume_text=resume_text,

                selected_role=role,

                difficulty=difficulty,

                total_questions=total_questions

            )

            # -----------------------------
            # Gemini Response
            # -----------------------------

            response = model.generate_content(
                prompt
            )

            output = response.text.strip()

            # -----------------------------
            # Remove Markdown
            # -----------------------------

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

            # -----------------------------
            # Parse JSON
            # -----------------------------

            interview_questions = json.loads(
                output
            )

            # -----------------------------
            # Create Interview Session
            # -----------------------------

            session = InterviewSession(

                document_id=document_id,

                selected_role=role,

                difficulty=difficulty,

                total_questions=total_questions,

                current_question=1,

                overall_score=0,

                technical_score=0,

                communication_score=0,

                coding_score=0,

                project_score=0,

                confidence_score=0,

                completeness_score=0,

                interview_status="IN_PROGRESS",

                questions_json=json.dumps(
                    interview_questions
                ),

                answers_json=json.dumps([]),

                feedback_json=json.dumps([]),

                interview_report=None

            )

            self.db.add(session)

            self.db.commit()

            self.db.refresh(session)

            return session

        except Exception as e:

            print(
                "Interview Session Error:",
                str(e)
            )

            self.db.rollback()

            return None

    # ====================================================
    # Get Interview Session
    # ====================================================

    def get_session(
        self,
        interview_id: int
    ):

        session = (

            self.db.query(
                InterviewSession
            )

            .filter(
                InterviewSession.id == interview_id
            )

            .first()

        )

        return session


    # ====================================================
    # Get Current Question
    # ====================================================

    def get_current_question(
        self,
        interview_id: int
    ):

        session = self.get_session(
            interview_id
        )

        if session is None:

            return None

        questions = json.loads(
            session.questions_json
        )

        question_list = questions["questions"]

        if session.current_question > len(question_list):

            return None

        return question_list[
            session.current_question - 1
        ]


    # ====================================================
    # Move To Next Question
    # ====================================================

    def move_to_next_question(
        self,
        interview_id: int
    ):

        session = self.get_session(
            interview_id
        )

        if session is None:

            return False

        session.current_question += 1

        if session.current_question > session.total_questions:

            session.interview_status = "COMPLETED"

        self.db.commit()

        return True


    # ====================================================
    # Check Interview Completed
    # ====================================================

    def is_interview_completed(
        self,
        interview_id: int
    ):

        session = self.get_session(
            interview_id
        )

        if session is None:

            return False

        return (
            session.interview_status
            == "COMPLETED"
        )


    # ====================================================
    # Complete Interview
    # ====================================================

    def complete_interview(
        self,
        interview_id: int
    ):

        session = self.get_session(
            interview_id
        )

        if session is None:

            return False

        session.interview_status = "COMPLETED"

        self.db.commit()

        return True


interview_session_service = InterviewSessionService()    