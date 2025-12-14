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
  ],
  "grammar": {
    "topic": "grammar topic in English or German",
    "explanation": "short explanation in German, max 6 sentences",
    "examples": ["Beispiel 1", "Beispiel 2", "Beispiel 3"],
    "exercises": [
      {"id": 1, "instruction": "German instruction", "prompt": "Ein Satz mit ____ Luecke", "answer": "expected answer", "answer_explanation": "Warum ist das korrekt"},
      {"id": 2, "instruction": "German instruction", "prompt": "Ein Satz mit ____ Luecke", "answer": "expected answer", "answer_explanation": "Warum ist das korrekt"},
      {"id": 3, "instruction": "German instruction", "prompt": "Ein Satz mit ____ Luecke", "answer": "expected answer", "answer_explanation": "Warum ist das korrekt"}
    ]
  }
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
- A grammar section with:
  - a grammar topic title (English or German),
  - a short explanation (German, max 6 sentences),
  - 3 to 5 example sentences in German,
  - exactly 3 exercises. Each exercise must include id (1, 2, 3), an instruction in German, a sentence with a blank using "____", the expected answer string, and optionally a short explanation (1-2 sentences) for the answer.

Remember: output only the JSON object, nothing else.
"""

    content = call_llm(
        [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]
    )

    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(line for line in cleaned.splitlines() if not line.strip().startswith("```"))

    try:
        plan = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            json_str = cleaned[start : end + 1]
            try:
                plan = json.loads(json_str)
            except json.JSONDecodeError:
                raise RuntimeError(f"Model returned non JSON content: {cleaned}")
        else:
            raise RuntimeError(f"Model returned non JSON content: {cleaned}")

    grammar = plan.get("grammar", {})
    examples = grammar.get("examples", [])
    exercises = grammar.get("exercises", [])

    if not isinstance(examples, list) or not 3 <= len(examples) <= 5:
        raise RuntimeError(f"Grammar examples must contain between 3 and 5 items. Raw content: {cleaned}")
    if not isinstance(exercises, list) or len(exercises) != 3:
        raise RuntimeError(f"Grammar exercises must contain exactly 3 items. Raw content: {cleaned}")

    return plan


def check_answers(reading_text, questions, answers_dict):
    """
    reading_text: str
    questions: list of {"id": int, "question": str}
    answers_dict: {id: user_answer_str}
    """
    prompt = "Hier ist ein deutscher Lesetext:\n\n"
    prompt += (reading_text or "") + "\n\n"
    prompt += (
        "Hier sind die Verstaendnisfragen und meine Antworten.\n"
        "Gib bitte auf Deutsch kurzes Feedback und die richtigen Antworten.\n"
    )

    for q in questions:
        qid = q.get("id")
        q_text = q.get("question", "")
        if qid is None:
            continue
        user_answer = answers_dict.get(qid, "")
        prompt += f"\nFrage {qid}: {q_text}\nMeine Antwort: {user_answer}\n"

    feedback = call_llm([{"role": "user", "content": prompt}])
    return feedback


def check_grammar(grammar, user_answers_dict):
    """
    grammar: dict from the plan["grammar"]
    user_answers_dict: {exercise_id: user_answer_string}
    returns: short German feedback string
    """
    topic = grammar.get("topic", "")
    explanation = grammar.get("explanation", "")
    examples = grammar.get("examples", [])
    exercises = grammar.get("exercises", [])

    prompt = (
        "Du bist ein freundlicher Deutschlehrer. "
        "Bewerte meine Grammatikuebungen und gib kurzes Feedback auf Deutsch. "
        "Fuer jede Uebung schreibe zuerst 'Richtig' oder 'Nicht ganz', "
        "falls falsch nenne die korrekte Loesung und eine knappe Erklaerung (1 Satz). "
        "Schliesse mit einem kurzen Tipp, der sich auf das Grammatikthema bezieht.\n\n"
    )
    prompt += f"Grammatikthema: {topic}\n"
    prompt += f"Erklaerung: {explanation}\n"
    prompt += "Beispiele:\n"
    for ex in examples:
        prompt += f"- {ex}\n"

    prompt += "\nUebungen mit erwarteten Antworten:\n"
    for exercise in exercises:
        eid = exercise.get("id")
        prompt_text = exercise.get("prompt", "")
        expected = exercise.get("answer", "")
        exp_expl = exercise.get("answer_explanation", "")
        prompt += (
            f"Uebung {eid}: {prompt_text}\n"
            f"Erwartete Antwort: {expected}\n"
            f"Erklaerung: {exp_expl}\n"
        )

    prompt += "\nMeine Antworten:\n"
    for exercise in exercises:
        eid = exercise.get("id")
        user_answer = user_answers_dict.get(eid, "")
        prompt += f"Uebung {eid}: {user_answer}\n"

    feedback = call_llm(
        [
            {"role": "user", "content": prompt},
        ]
    )
    return feedback
