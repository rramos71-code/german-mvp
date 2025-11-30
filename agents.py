import json
from llm_client import call_llm

def get_daily_plan():
    """
    Ask the model for a daily plan and parse the JSON response.
    """
    system_msg = """
You are a German teacher for a B1-B2 learner.

You must output a single valid JSON object.
It must be directly parseable by Python json.loads.
Do not add any explanation, comments, markdown, code fences, or text before or after the JSON.

Required schema:

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

    user_msg = """
Create the content for one study session with:
- One reading text in German, about 150 to 200 words.
- Exactly 3 comprehension questions in German.
- A small vocabulary list, 5 to 8 items, taken from the text, with:
  - the German word
  - a short English translation
  - one German example sentence.

Remember: output only the JSON object, nothing else.
"""

    content = call_llm(
        [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]
    )

    # Try to parse the whole content as JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Fallback: try to cut from first { to last }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            json_str = content[start : end + 1]
            return json.loads(json_str)
        # If this still fails, raise a helpful error for debugging
        raise RuntimeError(f"Model returned non JSON content: {content!r}")


def check_answers(reading_text, questions, answers_dict):
    """
    reading_text: str
    questions: list of {"id": int, "question": str}
    answers_dict: {id: user_answer_str}
    """
    prompt = "Hier ist ein deutscher Lesetext:\n\n"
    prompt += reading_text + "\n\n"
    prompt += (
        "Hier sind die Verständnisfragen und meine Antworten.\n"
        "Gib bitte auf Deutsch kurzes Feedback und die richtigen Antworten.\n"
    )

    for q in questions:
        qid = q["id"]
        q_text = q["question"]
        user_answer = answers_dict.get(qid, "")
        prompt += f"\nFrage {qid}: {q_text}\nMeine Antwort: {user_answer}\n"

    feedback = call_llm([{"role": "user", "content": prompt}])
    return feedback
