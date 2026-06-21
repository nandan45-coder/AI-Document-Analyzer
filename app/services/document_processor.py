from pypdf import PdfReader
from docx import Document
import os


def extract_pdf_text(file_path):
    """
    Extract text from PDF files
    """

    text = ""

    try:
        reader = PdfReader(file_path)

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

        return text

    except Exception as e:
        raise Exception(f"PDF extraction failed: {str(e)}")


def extract_docx_text(file_path):
    """
    Extract text from DOCX files
    """

    try:
        doc = Document(file_path)

        text = "\n".join(
            paragraph.text
            for paragraph in doc.paragraphs
        )

        return text

    except Exception as e:
        raise Exception(f"DOCX extraction failed: {str(e)}")


def extract_txt_text(file_path):
    """
    Extract text from TXT files
    """

    try:
        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()

    except UnicodeDecodeError:

        with open(
            file_path,
            "r",
            encoding="latin-1"
        ) as file:

            return file.read()

    except Exception as e:
        raise Exception(f"TXT extraction failed: {str(e)}")


def extract_text(file_path):
    """
    Universal document processor
    Automatically detects file type
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    extension = os.path.splitext(
        file_path
    )[1].lower()

    if extension == ".pdf":
        return extract_pdf_text(file_path)

    elif extension == ".docx":
        return extract_docx_text(file_path)

    elif extension == ".txt":
        return extract_txt_text(file_path)

    else:
        raise ValueError(
            f"Unsupported file type: {extension}"
        )