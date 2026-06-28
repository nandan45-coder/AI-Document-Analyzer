import json

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.interview_session import InterviewSession

from app.services.gemini_service import model


class InterviewEvaluatorService:

    def __init__(self):

        self.db: Session = SessionLocal()


    def evaluate_answer(

        self,

        interview_id: int,

        candidate_answer: str

    ):

        try:

            session = (

                self.db.query(
                    InterviewSession
                )

                .filter(
                    InterviewSession.id == interview_id
                )

                .first()

            )

            if session is None:

                return {

                    "success": False,

                    "message": "Interview not found."

                }

            questions = json.loads(
                session.interview_report
            )

            current = questions["questions"][
                session.current_question - 1
            ]

            prompt = f"""
You are a Senior Technical Interviewer.

Evaluate the candidate's answer.

Question

{current["question"]}

Expected Answer

{current["expected_answer"]}

Candidate Answer

{candidate_answer}

Evaluate on

1 Technical Accuracy

2 Communication

3 Completeness

4 Confidence

5 Overall Score

Return ONLY JSON.

Format

{{
    "technical_score":0,
    "communication_score":0,
    "confidence_score":0,
    "completeness_score":0,
    "overall_score":0,

    "feedback":"",

    "ideal_answer":"",

    "improvement_tips":[]
}}
"""

            response = model.generate_content(
                prompt
            )

            output = response.text.strip()

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

            evaluation = json.loads(output)

            session.technical_score += evaluation[
                "technical_score"
            ]

            session.communication_score += evaluation[
                "communication_score"
            ]

            session.confidence_score += evaluation[
                "confidence_score"
            ]

            session.overall_score += evaluation[
                "overall_score"
            ]

            session.current_question += 1

            if session.current_question > session.total_questions:

                session.interview_status = "COMPLETED"

            self.db.commit()

            return {

                "success": True,

                "question_completed": session.current_question - 1,

                "next_question": session.current_question,

                "evaluation": evaluation,

                "interview_completed":

                session.interview_status == "COMPLETED"

            }

        except Exception as e:

            return {

                "success": False,

                "error": str(e)

            }

        finally:

            self.db.close()
    
        # ====================================================
    # Generate Final Interview Report
    # ====================================================

    def get_final_report(
        self,
        interview_id: int
    ):

        try:

            session = (

                self.db.query(
                    InterviewSession
                )

                .filter(
                    InterviewSession.id == interview_id
                )

                .first()

            )

            if session is None:

                return {

                    "success": False,

                    "message": "Interview session not found."

                }

            total_questions = max(
                session.total_questions,
                1
            )

            # ---------------------------------------
            # Calculate Average Scores
            # ---------------------------------------

            technical_score = round(
                session.technical_score / total_questions,
                2
            )

            communication_score = round(
                session.communication_score / total_questions,
                2
            )

            confidence_score = round(
                session.confidence_score / total_questions,
                2
            )

            completeness_score = round(
                session.completeness_score / total_questions,
                2
            )

            overall_score = round(
                session.overall_score / total_questions,
                2
            )

            coding_score = round(
                session.coding_score / total_questions,
                2
            )

            project_score = round(
                session.project_score / total_questions,
                2
            )

            answers = json.loads(
                session.answers_json
            )

            feedback = json.loads(
                session.feedback_json
            )

            # ---------------------------------------
            # Gemini Report Generation
            # ---------------------------------------

            prompt = f"""
You are an Expert HR Recruiter.

Interview Summary

Role:
{session.selected_role}

Difficulty:
{session.difficulty}

Overall Score:
{overall_score}

Technical Score:
{technical_score}

Communication Score:
{communication_score}

Confidence Score:
{confidence_score}

Completeness Score:
{completeness_score}

Coding Score:
{coding_score}

Project Score:
{project_score}

Candidate Answers

{json.dumps(answers, indent=4)}

Evaluation

{json.dumps(feedback, indent=4)}

Generate

1 Top Strengths

2 Weak Areas

3 Personalized Study Plan

4 Career Advice

5 Interview Readiness

Return ONLY JSON.

Format

{{
    "top_strengths": [],
    "weak_areas": [],
    "study_plan": [],
    "career_advice": [],
    "interview_readiness": ""
}}
"""

            response = model.generate_content(
                prompt
            )

            output = response.text.strip()

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

            ai_report = json.loads(output)

            final_report = {

                "overall_score": overall_score,

                "technical_score": technical_score,

                "communication_score": communication_score,

                "confidence_score": confidence_score,

                "completeness_score": completeness_score,

                "coding_score": coding_score,

                "project_score": project_score,

                "top_strengths":
                    ai_report["top_strengths"],

                "weak_areas":
                    ai_report["weak_areas"],

                "study_plan":
                    ai_report["study_plan"],

                "career_advice":
                    ai_report["career_advice"],

                "interview_readiness":
                    ai_report["interview_readiness"]

            }

            session.interview_report = json.dumps(
                final_report
            )

            self.db.commit()

            return {

                "success": True,

                "interview_id": session.id,

                "selected_role": session.selected_role,

                "difficulty": session.difficulty,

                "report": final_report,

                "answers": answers,

                "feedback": feedback

            }

        except Exception as e:

            return {

                "success": False,

                "error": str(e)

            }

        finally:

            self.db.close()


interview_evaluator_service = InterviewEvaluatorService()