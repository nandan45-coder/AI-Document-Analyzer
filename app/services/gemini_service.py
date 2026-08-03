import os
import google.generativeai as genai

from dotenv import load_dotenv

load_dotenv()
env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(env_file):
    load_dotenv(dotenv_path=env_file)

api_key = os.getenv("GEMINI_API_KEY")
genai.configure(
    api_key=api_key
)

try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    print("MODEL LOADED: gemini-2.5-flash")
except Exception:
    model = genai.GenerativeModel("gemini-1.5-flash")
    print("MODEL LOADED: gemini-1.5-flash")


def generate_answer(
    question,
    context
):

    prompt = f"""
You are an AI Document Analyzer.

Instructions:
1. Answer ONLY from the provided context.
2. If the answer exists, give a direct concise answer.
3. Do not add assumptions.
4. If the answer is missing, reply:
   'The document does not contain this information.'
Context:
{context}

Question:
{question}
"""

    try:
        response = model.generate_content(
            prompt
        )

        return response.text
    except Exception as e:
        return f"Unable to generate answer due to AI service error: {str(e)}"

def generate_summary(
    text
):

    prompt = f"""
You are an AI Document Analyzer.

Generate a professional summary
of the document.

Document:

{text}

Summary:
"""

    try:
        response = model.generate_content(
            prompt
        )

        return response.text
    except Exception as e:
        return f"Unable to generate summary due to AI service error: {str(e)}"