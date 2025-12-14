import streamlit as st
from agents import (
    get_daily_plan,
    get_reading_block,
    get_grammar_block,
    get_grammar_exercises_only,
    check_answers,
    check_grammar,
)

st.set_page_config(page_title="German Coach MVP", layout="wide")

page = st.sidebar.selectbox("Navigation", ["Dashboard", "Today's session"])


def _clear_state_by_prefix(prefixes):
    for k in list(st.session_state.keys()):
        if any(k.startswith(p) for p in prefixes):
            del st.session_state[k]


if page == "Dashboard":
    st.title("German Learning Dashboard")
    st.write("For now, go to 'Today's session' to start a lesson.")


if page == "Today's session":
    st.title("Today's session")

    st.sidebar.subheader("Session settings")
    level = st.sidebar.radio("Level", ["B1", "B2"], index=0)
    topic = st.sidebar.selectbox(
        "Topic",
        ["Alltag", "Arbeit", "Reisen", "Gesundheit", "Meetings", "Small Talk"],
        index=0,
    )

    col_a, col_b, col_c, col_d = st.columns(4)

    with col_a:
        if st.button("Generate full plan"):
            _clear_state_by_prefix(["q_", "g_"])
            st.session_state.pop("feedback", None)
            st.session_state.pop("grammar_feedback", None)
            try:
                st.session_state.plan = get_daily_plan(level=level, topic=topic)
                st.session_state.plan_meta = {"level": level, "topic": topic}
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
                    reading_block = get_reading_block(level=level, topic=topic)
                    st.session_state.plan.update(reading_block)
                    st.session_state.plan_meta = {"level": level, "topic": topic}
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
                    st.session_state.plan_meta = {"level": level, "topic": topic}
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
            st.caption(f"Level: {meta.get('level', level)} | Topic: {meta.get('topic', topic)}")

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
        for q in plan.get("questions", []):
            qid = q.get("id")
            question_text = q.get("question", "")
            if qid is None:
                continue
            answers[qid] = st.text_input(question_text, key=f"q_{qid}")

        st.subheader("Vocabulary")
        vocab = plan.get("vocabulary", [])
        if vocab:
            for item in vocab:
                st.markdown(
                    f"- **{item.get('word', '')}**: {item.get('translation', '')}\n"
                    f"  _{item.get('example', '')}_"
                )
        else:
            st.info("No vocabulary items available.")

        if st.button("Check my answers"):
            if reading_text:
                feedback = check_answers(reading_text, plan.get("questions", []), answers)
                st.session_state.feedback = feedback
            else:
                st.warning("Cannot check answers without a reading text.")

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

                # Gated solutions toggle
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

            # New button: regenerate exercises only (same grammar topic)
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                if st.button("New grammar exercises"):
                    if "plan" not in st.session_state:
                        st.warning("Generate a full plan first.")
                    else:
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
            grammar_answers_live = {}
            for ex in exercises:
                eid = ex.get("id")
                instruction = ex.get("instruction", "")
                prompt = ex.get("prompt", "")
                if eid is None:
                    continue
                grammar_answers_live[eid] = st.text_input(f"{instruction}\n{prompt}", key=f"g_{eid}")

            if "grammar_feedback" in st.session_state:
                gfb = st.session_state.grammar_feedback

                if isinstance(gfb, dict):
                    for r in gfb.get("results", []):
                        st.markdown(f"**Übung {r.get('id')}** - {r.get('verdict')}")
                        st.markdown(f"- Korrekt: {r.get('correct_answer')}")
                        st.markdown(f"- Erklärung: {r.get('explanation')}")
                    if gfb.get("overall_tip"):
                        st.info(gfb.get("overall_tip"))

                    # Gated solutions toggle
                    if st.toggle("Show solutions (grammar)", value=False):
                        for ex in grammar.get("exercises", []):
                            st.markdown(f"**Übung {ex.get('id')} Lösung:** {ex.get('answer')}")
                            if ex.get("answer_explanation"):
                                st.markdown(f"- {ex.get('answer_explanation')}")

                else:
                    st.write(gfb)

        else:
            st.info("Grammar section not available in the plan.")

        # Session summary
        reading_score = None
        grammar_score = None

        fb = st.session_state.get("feedback")
        if isinstance(fb, dict):
            reading_score = sum(1 for r in fb.get("results", []) if r.get("verdict") == "correct")

        gfb = st.session_state.get("grammar_feedback")
        if isinstance(gfb, dict):
            grammar_score = sum(1 for r in gfb.get("results", []) if r.get("verdict") == "correct")

        if reading_score is not None or grammar_score is not None:
            st.subheader("Session summary")
            if reading_score is not None:
                st.metric("Reading", f"{reading_score}/3")
            if grammar_score is not None:
                st.metric("Grammar", f"{grammar_score}/3")
            if reading_score is not None and grammar_score is not None:
                st.success(f"Overall: {reading_score + grammar_score}/6 correct")
