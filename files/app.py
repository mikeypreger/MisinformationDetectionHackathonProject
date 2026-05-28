# app.py
import streamlit as st
# We will import our backend logic here later
# from council import run_council_debate

st.set_page_config(page_title="Misinfo Council", layout="wide")

st.title("⚖️ The LLM Fact-Checking Council")
st.write("Paste a suspicious claim or social media text below.")

user_input = st.text_area("Suspicious Text / Claim:")

if st.button("Summon the Council"):
    if user_input:
        st.info("The council is deliberating...")
        
        # TODO: Call your backend function here
        # verdict = run_council_debate(user_input)
        # st.write(verdict)
        
        st.success("Verdict reached! (Placeholder)")
    else:
        st.warning("Please enter some text first.")