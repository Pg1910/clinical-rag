
import sys
import os

# Add current directory to path so we can import app
sys.path.append(os.getcwd())

from app.llm import llm_answer

payload = {
    "case_id": "1", # Assuming case 1 exists or handled
    "question": "TEST QUESTION"
}

print("Calling llm_answer...")
try:
    result = llm_answer(payload)
    print("Result:", result)
except Exception as e:
    print("Exception:", e)
