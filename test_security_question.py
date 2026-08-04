"""
Integration test script for Phase 7 Security Question & Password Reset features.
"""

import sys
import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_security_question_flow():
    print("--- 0. Testing GET /auth/security-questions ---")
    sq_response = client.get("/auth/security-questions")
    print("Security Questions Status:", sq_response.status_code)
    print("Security Questions List:", sq_response.json())
    assert sq_response.status_code == 200
    questions = sq_response.json()["questions"]
    assert len(questions) >= 5

    print("\n--- 1. Testing Registration with Predefined Security Question ---")
    unique_suffix = uuid.uuid4().hex[:6]
    mobile_num = f"98{uuid.uuid4().int % 100000000:08d}"
    selected_question = questions[2]  # "What is your first school name?"
    reg_payload = {
        "full_name": "Nandkishor",
        "username": f"user_{unique_suffix}",
        "email": f"user_{unique_suffix}@example.com",
        "mobile": mobile_num,
        "password": "Nandan@1414",
        "confirm_password": "Nandan@1414",
        "security_question": selected_question,
        "security_answer": "ABC School"
    }
    
    response = client.post("/auth/register", json=reg_payload)
    print("Registration Status:", response.status_code)
    print("Registration Response:", response.json())
    assert response.status_code == 201, f"Registration failed: {response.text}"
    reg_data = response.json()
    assert reg_data["security_question"] == selected_question
    assert "security_answer" not in reg_data

    print("\n--- 2. Testing Login ---")
    login_payload = {
        "username_or_email": f"user_{unique_suffix}",
        "password": "Nandan@1414"
    }
    response = client.post("/auth/login", json=login_payload)
    print("Login Status:", response.status_code)
    assert response.status_code == 200

    print("\n--- 3. Testing Forgot Password Step 1: Retrieve Security Question ---")
    forgot_step1_payload = {
        "username_or_email": f"user_{unique_suffix}"
    }
    response = client.post("/auth/forgot-password", json=forgot_step1_payload)
    print("Forgot Step 1 Status:", response.status_code)
    print("Forgot Step 1 Response:", response.json())
    assert response.status_code == 200
    retrieved_question = response.json()["security_question"]
    assert retrieved_question == selected_question

    print("\n--- 4. Testing Forgot Password Step 2: Incorrect Security Answer ---")
    forgot_bad_answer = {
        "username_or_email": f"user_{unique_suffix}",
        "email": f"user_{unique_suffix}@example.com",
        "security_question": selected_question,
        "security_answer": "Wrong Answer",
        "new_password": "NewNandan@1414",
        "confirm_new_password": "NewNandan@1414"
    }
    response = client.post("/auth/forgot-password", json=forgot_bad_answer)
    print("Forgot Bad Answer Status:", response.status_code)
    print("Forgot Bad Answer Response:", response.json())
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect security answer."

    print("\n--- 5. Testing Forgot Password Step 2: Password Mismatch ---")
    forgot_mismatch = {
        "username_or_email": f"user_{unique_suffix}",
        "email": f"user_{unique_suffix}@example.com",
        "security_question": selected_question,
        "security_answer": "ABC School",
        "new_password": "NewNandan@1414",
        "confirm_new_password": "DifferentPassword123"
    }
    response = client.post("/auth/forgot-password", json=forgot_mismatch)
    print("Forgot Mismatch Status:", response.status_code)
    print("Forgot Mismatch Response:", response.json())
    assert response.status_code == 422

    print("\n--- 6. Testing Forgot Password Step 2: Success Reset ---")
    forgot_success = {
        "username_or_email": f"user_{unique_suffix}",
        "email": f"user_{unique_suffix}@example.com",
        "security_question": selected_question,
        "security_answer": "abc school", # case-insensitive test
        "new_password": "NewNandan@1414",
        "confirm_new_password": "NewNandan@1414"
    }
    response = client.post("/auth/forgot-password", json=forgot_success)
    print("Forgot Success Status:", response.status_code)
    print("Forgot Success Response:", response.json())
    assert response.status_code == 200
    assert response.json()["success"] is True

    print("\n--- 7. Testing Login with New Password ---")
    login_new_payload = {
        "username_or_email": f"user_{unique_suffix}",
        "password": "NewNandan@1414"
    }
    response = client.post("/auth/login", json=login_new_payload)
    print("Login with New Password Status:", response.status_code)
    assert response.status_code == 200
    print("Login successful with new reset password!")

    print("\nALL SECURITY QUESTION & PASSWORD RESET TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_security_question_flow()
