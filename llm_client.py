import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
API_URL = os.getenv("LLM_API_URL")
MODEL = os.getenv("LLM_MODEL")

def call_llm(messages, response_format=None):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1200,
    }

    if response_format is not None:
        payload["response_format"] = response_format

    resp = requests.post(API_URL, json=payload, headers=headers)
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        # This helps you debug in logs without leaking secrets
        print("Groq status:", resp.status_code)
        print("Groq body:", resp.text)
        raise

    data = resp.json()
    return data["choices"][0]["message"]["content"]
