import streamlit as st
from agents import get_daily_plan, check_answers

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
            st.session_state.plan = get_daily_plan()

    plan = st.session_state.get("plan")

    if plan:
        st.subheader("Reading topic")
        st.write(plan.get("reading_topic", ""))

        st.subheader("Reading text")
        st.write(plan["reading_text"])

        st.subheader("Questions")
        answers = {}
        for q in plan["questions"]:
            answers[q["id"]] = st.text_input(
                q["question"],
                key=f"q_{q['id']}"
            )

        st.subheader("Vocabulary from the text")
        for v in plan["vocabulary"]:
            st.markdown(
                f"- **{v['word']}** - {v['translation']}  \n"
                f"  _{v['example']}_"
            )

        if st.button("Check my answers"):
            feedback = check_answers(plan["reading_text"], plan["questions"], answers)
            st.session_state.feedback = feedback

        if "feedback" in st.session_state:
            st.subheader("Feedback")
            st.write(st.session_state.feedback)

