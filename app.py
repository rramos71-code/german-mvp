import streamlit as st
from agents import (
    get_daily_plan,
    get_reading_block,
    get_grammar_block,
    get_vocab_block,
    get_grammar_exercises_only,
    check_answers,
    check_grammar,
)
from storage import append_session, load_sessions, make_vocab_csv_rows, utc_now_iso

st.set_page_config(page_title="German Coach MVP", layout="wide")

page = st.sidebar.selectbox("Navigation", ["Dashboard", "Today's session"])


def _clear_state_by_prefix(prefixes):
    for k in list(st.session_state.keys()):
        if any(k.startswith(p) for p in prefixes):
            del st.session_state[k]


def _calc_scores():
    reading_score = None
    grammar_score = None

    fb = st.session_state.get("feedback")
    if isinstance(fb, dict):
        reading_score = sum(1 for r in fb.get("results", []) if r.get("verdict") == "correct")

    gfb = st.session_state.get("grammar_feedback")
    if isinstance(gfb, dict):
        grammar_score = sum(1 for r in gfb.get("results", []) if r.get("verdict") == "correct")

    return reading_score, grammar_score


def _session_params(session_length: str):
    if session_length == "10":
        return {"word_min": 120, "word_max": 160, "vocab_n": 5}
    return {"word_min": 180, "word_max": 240, "vocab_n": 8}


if page == "Dashboard":
    st.title("German Learning Dashboard")

    sessions = load_sessions(limit=30)
    if not sessions:
        st.info("No saved sessions yet. Go to 'Today's session' and click 'Save session'.")
    else:
        st.subheader("Recent sessions")
        for s in reversed(sessions):
            dt = s.get("timestamp", "")
            lv = s.get("level", "")
            tp = s.get("topic", "")
            rt = s.get("reading_topic", "")
            rs = s.get("reading_score")
            gs = s.get("grammar_score")
            st.markdown(f"- **{dt}** | {lv} | {tp} | {rt} | Reading: {rs}/3 | Grammar: {gs}/3")


if page == "Today's session":
    st.title("Today's session")

    st.sidebar.subheader("Session settings")
    level = st.sidebar.radio("Level", ["B1", "B2"], index=0)
    topic = st.sidebar.selectbox(
        "Topic",
        ["Alltag", "Arbeit", "Reisen", "Gesundheit", "Meetings", "Small Talk"],
        index=0,
    )
    session_length = st.sidebar.radio("Session length", ["10", "20"], index=1, format_func=lambda x: f"{x} min")

    params = _session_params(session_length)

    col_a, col_b, col_c, col_d = st.columns(4)

    with col_a:
        if st.button("Generate full plan"):
            _clear_state_by_prefix(["q_", "g_"])
            st.session_state.pop("feedback", None)
            st.session_state.pop("grammar_feedback", None)
            try:
                st.session_state.plan = get_daily_plan(level=level, topic=topic, session_length=session_length)
                st.session_state.plan_meta = {"level": level, "topic": topic, "session_length": session_length}
            except RuntimeError as e:
                st.error(f"Could not generate plan: {e}")

    with col_b:
        if st.button("Regenerate reading"):
            if "plan" not in st.session_state:
                st.warning("Generate a full plan first.")
            else:
                _clear_state_by_prefix(["q_"])
                st.session_state.pop("feedback", None)
                try:
                    reading_block = get_reading_block(
                        level=level,
                        topic=topic,
                        word_min=params["word_min"],
                        word_max=params["word_max"],
                        vocab_n=params["vocab_n"],
                    )
                    st.session_state.plan.update(reading_block)
                    st.session_state.plan_meta = {"level": level, "topic": topic, "session_length": session_length}
                except RuntimeError as e:
                    st.error(f"Could not regenerate reading: {e}")

    with col_c:
        if st.button("Regenerate grammar"):
            if "plan" not in st.session_state:
                st.warning("Generate a full plan first.")
            else:
                _clear_state_by_prefix(["g_"])
                st.session_state.pop("grammar_feedback", None)
                try:
                    reading_text = st.session_state.plan.get("reading_text", "")
                    grammar_block = get_grammar_block(level=level, topic=topic, reading_text=reading_text)
                    st.session_state.plan.update(grammar_block)
                    st.session_state.plan_meta = {"level": level, "topic": topic, "session_length": session_length}
                except RuntimeError as e:
                    st.error(f"Could not regenerate grammar: {e}")

    with col_d:
        if st.button("Reset session"):
            st.session_state.pop("plan", None)
            st.session_state.pop("plan_meta", None)
            st.session_state.pop("feedback", None)
            st.session_state.pop("grammar_feedback", None)
            _clear_state_by_prefix(["q_", "g_"])
            st.success("Session reset.")

    plan = st.session_state.get("plan")

    if not plan:
        st.info("Click 'Generate full plan' to start.")
    else:
        meta = st.session_state.get("plan_meta", {})
        if meta:
            st.caption(
                f"Level: {meta.get('level', level)} | Topic: {meta.get('topic', topic)} | Session: {meta.get('session_length', session_length)} min"
            )

        st.subheader("Reading topic")
        st.write(plan.get("reading_topic", ""))

        st.subheader("Reading text")
        reading_text = plan.get("reading_text")
        if reading_text:
            st.write(reading_text)
        else:
            st.warning("No reading text available in the plan.")

        st.subheader("Questions")
        answers = {}
        missing_qids = []

        for q in plan.get("questions", []):
            qid = q.get("id")
            question_text = q.get("question", "")
            if qid is None:
                continue
            val = st.text_input(question_text, key=f"q_{qid}")
            answers[qid] = val
            if not (val or "").strip():
                missing_qids.append(qid)

        if missing_qids:
            st.warning(f"Please answer all questions before checking. Missing: {', '.join(map(str, missing_qids))}")

        st.subheader("Vocabulary")

        col_v1, col_v2 = st.columns(2)
        with col_v1:
            if st.button("Regenerate vocabulary"):
                if not reading_text:
                    st.warning("No reading text found.")
                else:
                    st.session_state.pop("feedback", None)
                    try:
                        vb = get_vocab_block(level=level, topic=topic, reading_text=reading_text, n_items=params["vocab_n"])
                        st.session_state.plan["vocabulary"] = vb.get("vocabulary", [])
                        st.success("Vocabulary regenerated.")
                    except RuntimeError as e:
                        st.error(f"Could not regenerate vocabulary: {e}")

        with col_v2:
            csv_text = make_vocab_csv_rows(
                plan.get("vocabulary", []),
                level=meta.get("level", level),
                topic=meta.get("topic", topic),
            )
            st.download_button(
                "Export vocabulary (CSV)",
                data=csv_text.encode("utf-8"),
                file_name="vocabulary_export.csv",
                mime="text/csv",
            )

        vocab = plan.get("vocabulary", [])
        if vocab:
            for item in vocab:
                st.markdown(
                    f"- **{item.get('word', '')}**: {item.get('translation', '')}\n"
                    f"  _{item.get('example', '')}_"
                )
        else:
            st.info("No vocabulary items available.")

        check_disabled = (not reading_text) or (len(missing_qids) > 0)

        if st.button("Check my answers", disabled=check_disabled):
            feedback = check_answers(reading_text, plan.get("questions", []), answers)
            st.session_state.feedback = feedback
    
        if "feedback" in st.session_state:
            st.subheader("Feedback")
            fb = st.session_state.feedback
            if isinstance(fb, dict):
                for r in fb.get("results", []):
                    st.markdown(f"**Frage {r.get('id')}** - {r.get('verdict')}")
                    st.markdown(f"- Ideale Antwort: {r.get('ideal_answer')}")
                    st.markdown(f"- Tipp: {r.get('tip')}")
                if fb.get("overall_tip"):
                    st.info(fb.get("overall_tip"))

                if st.toggle("Show ideal answers (reading)", value=False):
                    for r in fb.get("results", []):
                        st.markdown(f"**Frage {r.get('id')} ideale Antwort:** {r.get('ideal_answer')}")
            else:
                st.write(fb)

        st.subheader("Grammar")
        grammar = plan.get("grammar")
        if grammar:
            st.write(f"**{grammar.get('topic', '')}**")
            st.write(grammar.get("explanation", ""))

            examples = grammar.get("examples", [])
            if examples:
                st.markdown("**Beispiele:**")
                for ex in examples:
                    st.markdown(f"- {ex}")

            col_g1, col_g2 = st.columns(2)
            with col_g1:
                if st.button("New grammar exercises"):
                    _clear_state_by_prefix(["g_"])
                    st.session_state.pop("grammar_feedback", None)
                    try:
                        grammar_topic = (st.session_state.plan.get("grammar") or {}).get("topic", "")
                        if not grammar_topic:
                            st.warning("No grammar topic found. Try 'Regenerate grammar' first.")
                        else:
                            new_ex = get_grammar_exercises_only(level=level, grammar_topic=grammar_topic)
                            st.session_state.plan["grammar"]["exercises"] = new_ex.get("exercises", [])
                            st.success("New exercises generated.")
                    except RuntimeError as e:
                        st.error(f"Could not regenerate grammar exercises: {e}")

            with col_g2:
                if st.button("Check grammar"):
                    exercises = grammar.get("exercises", [])
                    grammar_answers = {}
                    for ex in exercises:
                        eid = ex.get("id")
                        if eid is None:
                            continue
                        grammar_answers[eid] = st.session_state.get(f"g_{eid}", "")
                    feedback = check_grammar(grammar, grammar_answers)
                    st.session_state.grammar_feedback = feedback

            exercises = grammar.get("exercises", [])
            for ex in exercises:
                eid = ex.get("id")
                instruction = ex.get("instruction", "")
                prompt = ex.get("prompt", "")
                if eid is None:
                    continue
                st.text_input(f"{instruction}\n{prompt}", key=f"g_{eid}")

            if "grammar_feedback" in st.session_state:
                gfb = st.session_state.grammar_feedback
                if isinstance(gfb, dict):
                    for r in gfb.get("results", []):
                        st.markdown(f"**Übung {r.get('id')}** - {r.get('verdict')}")
                        st.markdown(f"- Korrekt: {r.get('correct_answer')}")
                        st.markdown(f"- Erklärung: {r.get('explanation')}")
                    if gfb.get("overall_tip"):
                        st.info(gfb.get("overall_tip"))

                    if st.toggle("Show solutions (grammar)", value=False):
                        for ex in grammar.get("exercises", []):
                            st.markdown(f"**Übung {ex.get('id')} Lösung:** {ex.get('answer')}")
                            if ex.get("answer_explanation"):
                                st.markdown(f"- {ex.get('answer_explanation')}")
                else:
                    st.write(gfb)
        else:
            st.info("Grammar section not available in the plan.")

        reading_score, grammar_score = _calc_scores()

        if reading_score is not None or grammar_score is not None:
            st.subheader("Session summary")
            if reading_score is not None:
                st.metric("Reading", f"{reading_score}/3")
            if grammar_score is not None:
                st.metric("Grammar", f"{grammar_score}/3")
            if reading_score is not None and grammar_score is not None:
                st.success(f"Overall: {reading_score + grammar_score}/6 correct")

        st.subheader("Save")

        if st.button("Save session"):
            ts = utc_now_iso()
            record = {
                "timestamp": ts,
                "level": meta.get("level", level),
                "topic": meta.get("topic", topic),
                "session_length": meta.get("session_length", session_length),
                "reading_topic": plan.get("reading_topic", ""),
                "reading_score": reading_score,
                "grammar_score": grammar_score,
                "vocabulary": plan.get("vocabulary", []),
            }
            append_session(record)
            st.success("Saved.")
