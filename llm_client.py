import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
API_URL = os.getenv("LLM_API_URL")
MODEL = os.getenv("LLM_MODEL")

def call_llm(messages):
    """
    messages: list of dicts like [{"role": "user", "content": "..."}, ...]
    returns: assistant message content as string
    """
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 512,
    }

    response = requests.post(API_URL, json=payload, headers=headers)

    # Helpful debugging: print error body instead of a blind 400
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        print("Error status:", response.status_code)
        print("Error body:", response.text)
        raise

    data = response.json()
    return data["choices"][0]["message"]["content"]
