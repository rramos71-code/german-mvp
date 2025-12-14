import streamlit as st
from agents import get_daily_plan, check_answers, check_grammar

st.set_page_config(page_title="German Coach MVP", layout="wide")

page = st.sidebar.selectbox("Navigation", ["Dashboard", "Today's session"])

if page == "Dashboard":
    st.title("German Learning Dashboard")
    st.write("For now, go to 'Today's session' to start a lesson.")

if page == "Today's session":
    st.title("Today's session")

    if "plan" not in st.session_state:
        st.info("Click the button to generate today's plan.")
        if st.button("Generate today's plan"):
            try:
                st.session_state.plan = get_daily_plan()
            except RuntimeError as e:
                st.error(f"Could not generate plan: {e}")
    elif st.button("Generate today's plan"):
        try:
            st.session_state.plan = get_daily_plan()
        except RuntimeError as e:
            st.error(f"Could not generate plan: {e}")

    plan = st.session_state.get("plan")

    if plan:
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
            answers[qid] = st.text_input(
                question_text,
                key=f"q_{qid}"
            )

        st.subheader("Vocabulary from the text")
        vocabulary = plan.get("vocabulary", [])
        if vocabulary:
            for v in vocabulary:
                word = v.get("word", "")
                translation = v.get("translation", "")
                example = v.get("example", "")
                st.markdown(
                    f"- **{word}** - {translation}  \n"
                    f"  _{example}_"
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
            st.write(st.session_state.feedback)

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

            exercises = grammar.get("exercises", [])
            grammar_answers = {}
            for exercise in exercises:
                eid = exercise.get("id")
                instruction = exercise.get("instruction", "")
                prompt = exercise.get("prompt", "")
                if eid is None:
                    continue
                grammar_answers[eid] = st.text_input(
                    f"{instruction}\n{prompt}",
                    key=f"g_{eid}"
                )

            if st.button("Check grammar"):
                feedback = check_grammar(grammar, grammar_answers)
                st.session_state.grammar_feedback = feedback

            if "grammar_feedback" in st.session_state:
                st.write(st.session_state.grammar_feedback)
        else:
            st.info("Grammar section not available in the plan.")
