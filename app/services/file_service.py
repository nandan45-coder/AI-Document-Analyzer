import os

ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt"]

def validate_file(filename):
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return False

    return True