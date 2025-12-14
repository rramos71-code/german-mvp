import json
from llm_client import call_llm


# -----------------------------
# JSON parsing helpers
# -----------------------------

def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        # remove any ```lang and ``` lines
        lines = []
        for line in t.splitlines():
            if line.strip().startswith("```"):
                continue
            lines.append(line)
        t = "\n".join(lines).strip()
    return t


def _extract_json_object(text: str) -> str:
    """
    Extract the first top-level JSON object substring from text, if present.
    """
    t = _strip_code_fences(text)
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return t
    return t[start : end + 1]


def _sanitize_json_string_breaks(text: str) -> str:
    """
    Fix a common LLM issue: inserting real newlines inside JSON string values.
    JSON does not allow raw newline characters inside quoted strings.
    We replace any \n or \r that occur while we are inside a JSON string with a space.

    This does NOT try to fix every possible JSON error, but it fixes the
    'Unterminated string' errors you saw in Streamlit logs.
    """
    t = _extract_json_object(text)

    out_chars = []
    in_string = False
    escape = False

    for ch in t:
        if in_string:
            if escape:
                # keep escaped char as-is
                out_chars.append(ch)
                escape = False
                continue

            if ch == "\\":
                out_chars.append(ch)
                escape = True
                continue

            if ch == '"':
                out_chars.append(ch)
                in_string = False
                continue

            # Replace raw line breaks inside strings
            if ch == "\n" or ch == "\r":
                out_chars.append(" ")
                continue

            out_chars.append(ch)
        else:
            if ch == '"':
                out_chars.append(ch)
                in_string = True
                continue
            out_chars.append(ch)

    return "".join(out_chars).strip()


def _try_parse_json(text: str):
    """
    Try multiple safe parse passes:
    1) direct json.loads on extracted object
    2) json.loads after sanitizing string line breaks
    """
    candidate = _extract_json_object(text)
    try:
        return json.loads(candidate), candidate
    except json.JSONDecodeError:
        sanitized = _sanitize_json_string_breaks(text)
        return json.loads(sanitized), sanitized


# -----------------------------
# Validation and normalization
# -----------------------------

def _ensure_list(value, default):
    return value if isinstance(value, list) else default


def _normalize_plan(plan: dict) -> dict:
    """
    Make sure the plan has the expected shape.
    Instead of crashing, we fill missing pieces with safe defaults.
    """
    if not isinstance(plan, dict):
        plan = {}

    plan.setdefault("reading_topic", "")
    plan.setdefault("reading_text", "")
    plan["questions"] = _ensure_list(plan.get("questions"), [])
    plan["vocabulary"] = _ensure_list(plan.get("vocabulary"), [])

    grammar = plan.get("grammar")
    if not isinstance(grammar, dict):
        grammar = {}
    grammar.setdefault("topic", "Grammatik")
    grammar.setdefault("explanation", "")
    grammar["examples"] = _ensure_list(grammar.get("examples"), [])
    grammar["exercises"] = _ensure_list(grammar.get("exercises"), [])
    plan["grammar"] = grammar

    # Clamp examples to 3-5 items (pad if needed)
    examples = grammar["examples"]
    examples = [str(x).strip() for x in examples if str(x).strip()]
    if len(examples) < 3:
        # pad with generic examples if missing
        while len(examples) < 3:
            examples.append("Beispiel: Ich habe heute Zeit.")
    if len(examples) > 5:
        examples = examples[:5]
    grammar["examples"] = examples

    # Ensure exactly 3 exercises with ids 1..3
    exercises = grammar["exercises"]
    normalized_ex = []
    for ex in exercises:
        if not isinstance(ex, dict):
            continue
        normalized_ex.append(ex)

    # If too many, trim
    normalized_ex = normalized_ex[:3]

    # If too few, pad
    while len(normalized_ex) < 3:
        missing_id = len(normalized_ex) + 1
        normalized_ex.append(
            {
                "id": missing_id,
                "instruction": "Setze das richtige Wort ein.",
                "prompt": "Ich ____ heute zu Hause.",
                "answer": "bin",
                "answer_explanation": "Hier steht das Verb „sein“ im Präsens: „ich bin“."
            }
        )

    # Enforce ids and required keys
    for idx, ex in enumerate(normalized_ex, start=1):
        ex["id"] = idx
        ex.setdefault("instruction", "Setze das richtige Wort ein.")
        ex.setdefault("prompt", "Ich ____ heute zu Hause.")
        if "____" not in ex["prompt"]:
            ex["prompt"] = ex["prompt"].strip() + " ____"
        ex.setdefault("answer", "")
        ex.setdefault("answer_explanation", "")

    grammar["exercises"] = normalized_ex
    plan["grammar"] = grammar

    return plan


# -----------------------------
# LLM repair helper
# -----------------------------

def _repair_plan_with_llm(raw_content: str) -> str:
    """
    Ask the LLM to convert malformed output into valid JSON.
    We explicitly instruct: no real line breaks inside string values.
    """
    repair_system = """
You are a strict JSON fixer.

Output ONLY a single valid JSON object. No markdown, no code fences, no comments.
Important JSON rules:
- Use double quotes for all strings.
- Do not include raw line breaks inside string values. If you need a line break, use a single space instead.

The JSON must match this schema:

{
  "reading_topic": "string",
  "reading_text": "string",
  "questions": [
    {"id": 1, "question": "string"},
    {"id": 2, "question": "string"},
    {"id": 3, "question": "string"}
  ],
  "vocabulary": [
    {"word": "German word", "translation": "English translation", "example": "German example sentence"}
  ],
  "grammar": {
    "topic": "string",
    "explanation": "German explanation, max 6 sentences",
    "examples": ["3 to 5 German example sentences"],
    "exercises": [
      {"id": 1, "instruction": "German instruction", "prompt": "Sentence with ____", "answer": "expected answer", "answer_explanation": "1-2 sentence German explanation"},
      {"id": 2, "instruction": "German instruction", "prompt": "Sentence with ____", "answer": "expected answer", "answer_explanation": "1-2 sentence German explanation"},
      {"id": 3, "instruction": "German instruction", "prompt": "Sentence with ____", "answer": "expected answer", "answer_explanation": "1-2 sentence German explanation"}
    ]
  }
}

Hard constraints:
- grammar.examples length is between 3 and 5.
- grammar.exercises length is exactly 3.
- Each exercise prompt contains "____".
"""
    repair_user = f"Fix this into valid JSON following the schema. Input:\n\n{raw_content}"
    return call_llm(
        [
            {"role": "system", "content": repair_system},
            {"role": "user", "content": repair_user},
        ]
    )


# -----------------------------
# Public API used by app.py
# -----------------------------

def get_daily_plan():
    system_msg = """
You are a German teacher for a B1-B2 learner.

Return ONLY a single valid JSON object (no markdown, no code fences, no extra text).
JSON must be parseable by Python json.loads.
Do not include raw line breaks inside string values. Use spaces instead.

Schema:

{
  "reading_topic": "short description in English",
  "reading_text": "German text (150-200 words)",
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
Create one study session:
- Reading: German text 150 to 200 words.
- Questions: exactly 3 comprehension questions in German.
- Vocabulary: 5 to 8 items from the text (word, English translation, German example sentence).
- Grammar:
  - topic title (English or German)
  - explanation in German (max 6 sentences)
  - examples: 3 to 5 German example sentences
  - exercises: exactly 3 exercises with ids 1,2,3. Each has instruction, prompt with "____", expected answer, and a short answer_explanation.
Remember: output ONLY the JSON object.
"""

    content = call_llm(
        [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]
    )

    # Parse with sanitization. If it fails, repair via LLM, then parse again.
    try:
        plan, _ = _try_parse_json(content)
    except Exception:
        repaired = _repair_plan_with_llm(content)
        plan, _ = _try_parse_json(repaired)

    plan = _normalize_plan(plan)
    return plan


def check_answers(reading_text, questions, answers_dict):
    prompt = "Hier ist ein deutscher Lesetext:\n\n"
    prompt += (reading_text or "") + "\n\n"
    prompt += (
        "Hier sind die Verständnisfragen und meine Antworten.\n"
        "Gib bitte auf Deutsch kurzes Feedback und die richtigen Antworten.\n"
    )

    for q in questions or []:
        qid = q.get("id")
        q_text = q.get("question", "")
        if qid is None:
            continue
        user_answer = (answers_dict or {}).get(qid, "")
        prompt += f"\nFrage {qid}: {q_text}\nMeine Antwort: {user_answer}\n"

    return call_llm([{"role": "user", "content": prompt}])


def check_grammar(grammar, user_answers_dict):
    topic = (grammar or {}).get("topic", "")
    explanation = (grammar or {}).get("explanation", "")
    examples = (grammar or {}).get("examples", [])
    exercises = (grammar or {}).get("exercises", [])

    prompt = (
        "Du bist ein freundlicher Deutschlehrer (B1-B2). "
        "Bewerte meine Grammatikübungen und gib kurzes Feedback auf Deutsch.\n"
        "Für jede Übung schreibe zuerst 'Richtig' oder 'Nicht ganz'. "
        "Falls falsch: nenne die korrekte Lösung und eine knappe Erklärung (1 Satz).\n"
        "Schließe mit einem kurzen Tipp, der sich auf das Grammatikthema bezieht.\n\n"
    )
    prompt += f"Grammatikthema: {topic}\n"
    prompt += f"Erklärung: {explanation}\n"
    prompt += "Beispiele:\n"
    for ex in examples or []:
        prompt += f"- {ex}\n"

    prompt += "\nÜbungen (mit erwarteten Antworten):\n"
    for exercise in exercises or []:
        eid = exercise.get("id")
        prompt_text = exercise.get("prompt", "")
        expected = exercise.get("answer", "")
        exp_expl = exercise.get("answer_explanation", "")
        prompt += (
            f"Übung {eid}: {prompt_text}\n"
            f"Erwartete Antwort: {expected}\n"
            f"Erklärung: {exp_expl}\n"
        )

    prompt += "\nMeine Antworten:\n"
    for exercise in exercises or []:
        eid = exercise.get("id")
        user_answer = (user_answers_dict or {}).get(eid, "")
        prompt += f"Übung {eid}: {user_answer}\n"

    return call_llm([{"role": "user", "content": prompt}])
