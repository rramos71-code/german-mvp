import json
import re
from llm_client import call_llm


def _safe_json_loads(text: str) -> dict:
    t = (text or "").strip()

    # Best effort: isolate first JSON object
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        t = t[start : end + 1]

    return json.loads(t)


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

    # Examples: 3..5
    examples = [str(x).strip() for x in grammar["examples"] if str(x).strip()]
    while len(examples) < 3:
        examples.append("Beispiel: Ich habe heute Zeit.")
    if len(examples) > 5:
        examples = examples[:5]
    grammar["examples"] = examples

    # Exercises: exactly 3
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


def _word_in_text(word: str, text: str) -> bool:
    # Robust matching, avoids false positives for short strings
    w = (word or "").strip()
    if not w:
        return False
    t = (text or "")
    pattern = r"\b" + re.escape(w) + r"\b"
    return re.search(pattern, t, flags=re.IGNORECASE) is not None


def _validate_vocab(vocab: list, reading_text: str, n_exact: int) -> None:
    if not isinstance(vocab, list):
        raise RuntimeError("Vocabulary is not a list")
    if len(vocab) != n_exact:
        raise RuntimeError("Vocabulary length invalid")

    seen = set()

    for item in vocab:
        if not isinstance(item, dict):
            raise RuntimeError("Vocabulary item not a dict")
        w = (item.get("word") or "").strip()
        if not w:
            raise RuntimeError("Vocabulary word missing")

        w_lower = w.lower()
        if w_lower in seen:
            raise RuntimeError("Duplicate vocabulary word")
        seen.add(w_lower)

        if reading_text and not _word_in_text(w, reading_text):
            raise RuntimeError(f"Vocabulary word not found in reading text: {w}")


def _session_params(session_length: str):
    if session_length == "10":
        return {"word_min": 120, "word_max": 160, "vocab_n": 5}
    return {"word_min": 180, "word_max": 240, "vocab_n": 8}


def get_reading_block(level="B1", topic="Alltag", word_min=150, word_max=200, vocab_n=8) -> dict:
    system_msg = f"""
You are a German teacher for a {level} learner.
Return ONLY a single valid JSON object.

Schema:
{{
  "reading_topic": "short description in English",
  "reading_text": "German text",
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
- reading_text length: {word_min}-{word_max} words
- questions: exactly 3 with ids 1,2,3
- vocabulary length: exactly {vocab_n}
- vocabulary words must be taken from the reading_text
- topic: "{topic}"
"""

    user_msg = f"""
Create a reading session for topic "{topic}" at level {level}.
Return ONLY the JSON object.
"""

    content = call_llm(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=1700,
    )
    return _safe_json_loads(content)


def get_vocab_block(level: str, topic: str, reading_text: str, n_items: int) -> dict:
    system_msg = f"""
You are a German teacher for a {level} learner.
Return ONLY a single valid JSON object.

Schema:
{{
  "vocabulary": [
    {{"word": "German word from the text", "translation": "English", "example": "German example sentence"}}
  ]
}}

Hard constraints:
- vocabulary length exactly {n_items}
- every 'word' must appear in the given reading_text
- all words must be unique
"""

    user_msg = f"""
From this reading text, extract exactly {n_items} useful vocabulary items.
Return ONLY the JSON object.

Topic: "{topic}"
Reading text:
\"\"\"{reading_text}\"\"\"
"""

    content = call_llm(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=900,
    )
    return _safe_json_loads(content)


def get_grammar_block(level="B1", topic="Alltag", reading_text="") -> dict:
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
- grammar.exercises length is exactly 3 with ids 1..3
- each exercise prompt contains "____"
"""

    reading_context = (reading_text or "").strip()

    user_msg = f"""
Create a grammar section for topic "{topic}" at level {level}.
Align the grammar point with the reading text if possible.

Reading text:
\"\"\"{reading_context}\"\"\"

Return ONLY the JSON object.
"""

    content = call_llm(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=1200,
    )
    return _safe_json_loads(content)


def get_grammar_exercises_only(level: str, grammar_topic: str) -> dict:
    system_msg = f"""
You are a German teacher for a {level} learner.
Return ONLY JSON.

Schema:
{{
  "exercises": [
    {{"id": 1, "instruction": "German instruction", "prompt": "Ein Satz mit ____", "answer": "expected", "answer_explanation": "German"}},
    {{"id": 2, "instruction": "German instruction", "prompt": "Ein Satz mit ____", "answer": "expected", "answer_explanation": "German"}},
    {{"id": 3, "instruction": "German instruction", "prompt": "Ein Satz mit ____", "answer": "expected", "answer_explanation": "German"}}
  ]
}}

Hard constraints:
- length exactly 3, ids 1..3
- each prompt contains "____"
- match topic: "{grammar_topic}"
"""

    user_msg = f"""
Create 3 new fill-in-the-blank exercises for grammar topic "{grammar_topic}" at level {level}.
Return ONLY the JSON object.
"""

    content = call_llm(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=900,
    )
    return _safe_json_loads(content)


def get_daily_plan(level="B1", topic="Alltag", session_length="20") -> dict:
    params = _session_params(session_length)
    vocab_n = params["vocab_n"]

    reading_block = get_reading_block(
        level=level,
        topic=topic,
        word_min=params["word_min"],
        word_max=params["word_max"],
        vocab_n=vocab_n,
    )

    reading_text = reading_block.get("reading_text", "")
    vocab = reading_block.get("vocabulary", [])

    try:
        _validate_vocab(vocab, reading_text, vocab_n)
    except Exception:
        vb = get_vocab_block(level=level, topic=topic, reading_text=reading_text, n_items=vocab_n)
        reading_block["vocabulary"] = vb.get("vocabulary", [])

    grammar_block = get_grammar_block(level=level, topic=topic, reading_text=reading_text)

    plan = {}
    plan.update(reading_block)
    plan.update(grammar_block)

    plan = _normalize_plan(plan)
    _validate_plan(plan)
    return plan


def check_answers(reading_text, questions, answers_dict):
    system_msg = """
Return ONLY a single valid JSON object.

Schema:
{
  "results": [
    {"id": 1, "verdict": "correct|partly|incorrect", "ideal_answer": "German", "tip": "German", "reason": "missing|content"},
    {"id": 2, "verdict": "correct|partly|incorrect", "ideal_answer": "German", "tip": "German", "reason": "missing|content"},
    {"id": 3, "verdict": "correct|partly|incorrect", "ideal_answer": "German", "tip": "German", "reason": "missing|content"}
  ],
  "overall_tip": "German"
}

Hard rules:
- If the user's answer is empty, whitespace, or missing, verdict MUST be "incorrect" and reason MUST be "missing".
- tips: one short sentence in German.
"""

    prompt = "Hier ist ein deutscher Lesetext:\n\n"
    prompt += (reading_text or "") + "\n\n"
    prompt += "Bewerte meine Antworten zu den Verständnisfragen.\n\n"

    for q in questions or []:
        qid = q.get("id")
        q_text = q.get("question", "")
        if qid is None:
            continue
        user_answer = (answers_dict or {}).get(qid, "")
        prompt += f"Frage {qid}: {q_text}\nMeine Antwort: {user_answer}\n\n"

    content = call_llm(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=900,
    )
    data = _safe_json_loads(content)

    # Normalize grader output to ids 1..3
    results = data.get("results", [])
    by_id = {r.get("id"): r for r in results if isinstance(r, dict)}
    normalized = []
    for i in [1, 2, 3]:
        r = by_id.get(i, {})
        normalized.append(
            {
                "id": i,
                "verdict": r.get("verdict", "incorrect"),
                "ideal_answer": r.get("ideal_answer", ""),
                "tip": r.get("tip", ""),
                "reason": r.get("reason", "content"),
            }
        )
    data["results"] = normalized
    data.setdefault("overall_tip", "")
    return data


def check_grammar(grammar, user_answers_dict):
    system_msg = """
Return ONLY a single valid JSON object.

Schema:
{
  "results": [
    {"id": 1, "verdict": "correct|incorrect", "correct_answer": "string", "explanation": "German", "reason": "missing|content"},
    {"id": 2, "verdict": "correct|incorrect", "correct_answer": "string", "explanation": "German", "reason": "missing|content"},
    {"id": 3, "verdict": "correct|incorrect", "correct_answer": "string", "explanation": "German", "reason": "missing|content"}
  ],
  "overall_tip": "German"
}

Hard rules:
- If the user's answer is empty, whitespace, or missing, verdict MUST be "incorrect" and reason MUST be "missing".
- explanation: one short sentence
- overall_tip: one short sentence
"""

    topic = (grammar or {}).get("topic", "")
    explanation = (grammar or {}).get("explanation", "")
    exercises = (grammar or {}).get("exercises", [])

    prompt = (
        "Bewerte meine Antworten zu den Grammatikübungen.\n"
        "Antworte streng nach dem JSON Schema.\n\n"
        f"Thema: {topic}\n"
        f"Erklärung: {explanation}\n\n"
    )

    for ex in exercises or []:
        eid = ex.get("id")
        instruction = ex.get("instruction", "")
        prompt_text = ex.get("prompt", "")
        expected = ex.get("answer", "")
        user_answer = (user_answers_dict or {}).get(eid, "")
        prompt += (
            f"Übung {eid}:\n"
            f"Anweisung: {instruction}\n"
            f"Aufgabe: {prompt_text}\n"
            f"Erwartete Antwort: {expected}\n"
            f"Meine Antwort: {user_answer}\n\n"
        )

    content = call_llm(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=900,
    )
    data = _safe_json_loads(content)

    # Normalize ids 1..3
    results = data.get("results", [])
    by_id = {r.get("id"): r for r in results if isinstance(r, dict)}
    normalized = []
    for i in [1, 2, 3]:
        r = by_id.get(i, {})
        normalized.append(
            {
                "id": i,
                "verdict": r.get("verdict", "incorrect"),
                "correct_answer": r.get("correct_answer", ""),
                "explanation": r.get("explanation", ""),
                "reason": r.get("reason", "content"),
            }
        )
    data["results"] = normalized
    data.setdefault("overall_tip", "")
    return data
