import json
from llm_client import call_llm


def _safe_json_loads(text: str) -> dict:
    t = (text or "").strip()
    if not t.startswith("{"):
        start = t.find("{")
        end = t.rfind("}")
        if start != -1 and end != -1 and end > start:
            t = t[start : end + 1]
    return json.loads(t)


def get_reading_block(level: str = "B1", topic: str = "Alltag") -> dict:
    system_msg = f"""
You are a German teacher for a {level} learner.

Return ONLY a single valid JSON object (no markdown, no code fences, no extra text).

Schema:
{{
  "reading_topic": "short description in English",
  "reading_text": "German text (150-200 words)",
  "questions": [
    {{"id": 1, "question": "German question 1"}},
    {{"id": 2, "question": "German question 2"}},
    {{"id": 3, "question": "German question 3"}}
  ],
  "vocabulary": [
    {{"word": "German", "translation": "English", "example": "German example sentence"}}
  ]
}}

Hard constraints:
- questions length is exactly 3 and ids are 1,2,3
- vocabulary length is 5 to 8
- The reading must match the topic "{topic}" and be appropriate for {level}.
"""

    user_msg = f"""
Create a reading-based study session for the topic "{topic}" at level {level}.

Requirements:
- reading_text: 150 to 200 words in German
- questions: exactly 3 comprehension questions in German
- vocabulary: 5 to 8 items taken from the text, each with:
  - word (German)
  - translation (English)
  - example (German example sentence)

Return ONLY the JSON object.
"""

    content = call_llm(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=1400,
    )
    return _safe_json_loads(content)


def get_grammar_block(level: str = "B1", topic: str = "Alltag", reading_text: str = "") -> dict:
    system_msg = f"""
You are a German teacher for a {level} learner.

Return ONLY a single valid JSON object.

Schema:
{{
  "grammar": {{
    "topic": "grammar topic in English or German",
    "explanation": "short explanation in German, max 6 sentences",
    "examples": ["Beispiel 1", "Beispiel 2", "Beispiel 3"],
    "exercises": [
      {{"id": 1, "instruction": "German instruction", "prompt": "Ein Satz mit ____", "answer": "expected answer", "answer_explanation": "Warum ist das korrekt"}},
      {{"id": 2, "instruction": "German instruction", "prompt": "Ein Satz mit ____", "answer": "expected answer", "answer_explanation": "Warum ist das korrekt"}},
      {{"id": 3, "instruction": "German instruction", "prompt": "Ein Satz mit ____", "answer": "expected answer", "answer_explanation": "Warum ist das korrekt"}}
    ]
  }}
}}

Hard constraints:
- grammar.examples length is 3 to 5
- grammar.exercises length is exactly 3 with ids 1,2,3
- each exercise prompt contains "____"
- Difficulty and wording should match level {level}
"""

    reading_context = (reading_text or "").strip()

    user_msg = f"""
Create a grammar section for the topic "{topic}" at level {level}.

If possible, align the grammar point and examples with this reading text:
\"\"\"{reading_context}\"\"\"

Requirements:
- Choose one grammar focus that fits {level} and matches the topic
- explanation: German, max 6 sentences
- examples: 3 to 5 German example sentences
- exercises: exactly 3 fill-in-the-blank exercises using "____", include answer and answer_explanation

Return ONLY the JSON object.
"""

    content = call_llm(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=1200,
    )
    return _safe_json_loads(content)


def get_daily_plan(level: str = "B1", topic: str = "Alltag") -> dict:
    try:
        reading_block = get_reading_block(level=level, topic=topic)
    except Exception as e:
        raise RuntimeError(f"Failed to generate reading block: {e}")

    reading_text = reading_block.get("reading_text", "")

    try:
        grammar_block = get_grammar_block(level=level, topic=topic, reading_text=reading_text)
    except Exception as e:
        raise RuntimeError(f"Failed to generate grammar block: {e}")

    plan = {}
    plan.update(reading_block)
    plan.update(grammar_block)

    plan = _normalize_plan(plan)
    _validate_plan(plan)
    return plan


def _normalize_plan(plan: dict) -> dict:
    if not isinstance(plan, dict):
        plan = {}

    plan.setdefault("reading_topic", "")
    plan.setdefault("reading_text", "")
    if not isinstance(plan.get("questions"), list):
        plan["questions"] = []
    if not isinstance(plan.get("vocabulary"), list):
        plan["vocabulary"] = []

    grammar = plan.get("grammar")
    if not isinstance(grammar, dict):
        grammar = {}
    grammar.setdefault("topic", "Grammatik")
    grammar.setdefault("explanation", "")
    if not isinstance(grammar.get("examples"), list):
        grammar["examples"] = []
    if not isinstance(grammar.get("exercises"), list):
        grammar["exercises"] = []
    plan["grammar"] = grammar

    examples = [str(x).strip() for x in grammar["examples"] if str(x).strip()]
    if len(examples) < 3:
        while len(examples) < 3:
            examples.append("Beispiel: Ich habe heute Zeit.")
    if len(examples) > 5:
        examples = examples[:5]
    grammar["examples"] = examples

    exercises = [x for x in grammar["exercises"] if isinstance(x, dict)]
    exercises = exercises[:3]
    while len(exercises) < 3:
        new_id = len(exercises) + 1
        exercises.append(
            {
                "id": new_id,
                "instruction": "Setze das richtige Wort ein.",
                "prompt": "Ich ____ heute zu Hause.",
                "answer": "bin",
                "answer_explanation": "Hier steht das Verb „sein“ im Präsens: „ich bin“.",
            }
        )

    for i, ex in enumerate(exercises, start=1):
        ex["id"] = i
        ex.setdefault("instruction", "Setze das richtige Wort ein.")
        ex.setdefault("prompt", "Ich ____ heute zu Hause.")
        if "____" not in ex["prompt"]:
            ex["prompt"] = ex["prompt"].strip() + " ____"
        ex.setdefault("answer", "")
        ex.setdefault("answer_explanation", "")

    grammar["exercises"] = exercises
    plan["grammar"] = grammar
    return plan


def _validate_plan(plan: dict) -> None:
    grammar = plan.get("grammar", {})
    examples = grammar.get("examples", [])
    exercises = grammar.get("exercises", [])

    if not (isinstance(examples, list) and 3 <= len(examples) <= 5):
        raise RuntimeError("Invalid grammar.examples length")

    if not (isinstance(exercises, list) and len(exercises) == 3):
        raise RuntimeError("Invalid grammar.exercises length")

    for ex in exercises:
        if "____" not in ex.get("prompt", ""):
            raise RuntimeError("Exercise prompt missing ____")


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

    return call_llm([{"role": "user", "content": prompt}], temperature=0.2, max_tokens=600)


def check_grammar(grammar, user_answers_dict):
    topic = (grammar or {}).get("topic", "")
    explanation = (grammar or {}).get("explanation", "")
    examples = (grammar or {}).get("examples", [])
    exercises = (grammar or {}).get("exercises", [])

    prompt = (
        "Du bist ein freundlicher Deutschlehrer (B1-B2). "
        "Bewerte meine Grammatikübungen und gib kurzes Feedback auf Deutsch.\n"
        "Für jede Übung: 'Richtig' oder 'Nicht ganz'. "
        "Falls falsch: korrekte Lösung und eine knappe Erklärung (1 Satz).\n"
        "Zum Schluss: ein kurzer Tipp zum Grammatikthema.\n\n"
        f"Grammatikthema: {topic}\n"
        f"Erklärung: {explanation}\n"
        "Beispiele:\n"
    )

    for ex in examples or []:
        prompt += f"- {ex}\n"

    prompt += "\nÜbungen:\n"
    for exercise in exercises or []:
        eid = exercise.get("id")
        prompt_text = exercise.get("prompt", "")
        expected = exercise.get("answer", "")
        prompt += f"Übung {eid}: {prompt_text}\nErwartete Antwort: {expected}\n"

    prompt += "\nMeine Antworten:\n"
    for exercise in exercises or []:
        eid = exercise.get("id")
        user_answer = (user_answers_dict or {}).get(eid, "")
        prompt += f"Übung {eid}: {user_answer}\n"

    return call_llm([{"role": "user", "content": prompt}], temperature=0.2, max_tokens=700)
