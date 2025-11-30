import json
from llm_client import call_llm

DAILY_PLAN_PROMPT = """
You are a German teacher for a B1-B2 learner.

Task:
Create the content for one study session with:
- One reading text in German, about 150 to 200 words.
- Exactly 3 comprehension questions in German.
- A small vocabulary list, 5 to 8 items, taken from the text, with:
  - the German word
  - a short English translation
  - one German example sentence.

Output JSON only, no explanations, with this schema:

{
  "reading_topic": "short description in English",
  "reading_text": "German text",
  "questions": [
    {"id": 1, "question": "German question 1"},
    {"id": 2, "question": "German question 2"},
    {"id": 3, "question": "German question 3"}
  ],
  "vocabulary": [
    {"word": "German", "translation": "English", "example": "German example sentence"}
  ]
}
"""

def get_daily_plan():
    content = call_llm([{"role": "user", "content": DAILY_PLAN_PROMPT}])

    # Make it robust to extra text around the JSON
    start = content.find("{")
    end = content.rfind("}")
    json_str = content[start:end + 1]

    return json.loads(json_str)


def check_answers(reading_text, questions, answers_dict):
    """
    reading_text: str
    questions: list of {"id": int, "question": str}
    answers_dict: {id: user_answer_str}
    """
    prompt = "Here is a German reading text:\n\n"
    prompt += reading_text + "\n\n"
    prompt += "Here are the comprehension questions and my answers.\n"
    prompt += "Please respond in German with brief feedback and give the correct answers.\n"

    for q in questions:
        qid = q["id"]
        q_text = q["question"]
        user_answer = answers_dict.get(qid, "")
        prompt += f"\nFrage {qid}: {q_text}\nMeine Antwort: {user_answer}\n"

    feedback = call_llm([{"role": "user", "content": prompt}])
    return feedback
