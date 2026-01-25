
import httpx
import json

url = "http://localhost:11434/api/generate"
payload = {
    "model": "qwen3:4b",
    "prompt": "Why is the sky blue?",
    "stream": False
}

print("Testing simple prompt...")
try:
    response = httpx.post(url, json=payload, timeout=60)
    print("Status:", response.status_code)
    print("Response JSON:", response.json())
except Exception as e:
    print("Error:", e)

print("-" * 20)
print("Testing with JSON format...")
payload_json = {
    "model": "qwen3:4b",
    "prompt": "Give me a JSON object with 'color': 'blue'.",
    "format": "json",
    "stream": False
}
try:
    response = httpx.post(url, json=payload_json, timeout=60)
    print("Status:", response.status_code)
    print("Response JSON:", response.json())
except Exception as e:
    print("Error:", e)
