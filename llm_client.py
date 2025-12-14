import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
API_URL = os.getenv("LLM_API_URL")
MODEL = os.getenv("LLM_MODEL")


class LLMConfigError(RuntimeError):
    pass


def _validate_config():
    missing = []
    if not API_KEY:
        missing.append("LLM_API_KEY")
    if not API_URL:
        missing.append("LLM_API_URL")
    if not MODEL:
        missing.append("LLM_MODEL")

    if missing:
        raise LLMConfigError(f"Missing environment variables: {', '.join(missing)}")

    if not API_URL.startswith("http"):
        raise LLMConfigError("LLM_API_URL must start with http or https")


def call_llm(messages, response_format=None, temperature=0.2, max_tokens=1400, timeout_s=30, retries=2):
    _validate_config()

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if response_format is not None:
        payload["response_format"] = response_format

    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(API_URL, json=payload, headers=headers, timeout=timeout_s)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue

    # Print details when HTTP error exists
    if isinstance(last_err, requests.exceptions.HTTPError):
        try:
            print("LLM status:", resp.status_code)
            print("LLM body:", resp.text)
        except Exception:
            pass

    raise last_err
