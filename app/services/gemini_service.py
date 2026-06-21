import os
import google.generativeai as genai

from dotenv import load_dotenv

load_dotenv()

genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

model = genai.GenerativeModel(
    "gemini-2.5-flash"
)
print("MODEL LOADED: gemini-2.5-flash")


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

    response = model.generate_content(
        prompt
    )

    return response.text

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

    response = model.generate_content(
        prompt
    )

    return response.text