"""
app.py

Streamlit front-end for the NL-to-SQL agent.

Run with:
    streamlit run app.py
"""

import streamlit as st
from agent import ask_agent

st.set_page_config(page_title="NL-to-SQL Agent", page_icon="🗃️")

st.title("🗃️ Ask Your Database")
st.caption("Ask questions in plain English -- the agent writes and runs the SQL for you.")

# --- Session state: keeps chat history across reruns (Streamlit reruns the
# whole script on every interaction, so we must store history ourselves) ---
if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {"role": "user"/"assistant", "content": str, "trace": list}

# --- Render past chat history ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        # If this message has a trace (tool calls), show it collapsed
        if msg.get("trace"):
            with st.expander("🔍 See how the agent got this answer"):
                for step in msg["trace"]:
                    st.markdown(f"**Called `{step['tool_name']}`**")
                    if step["tool_input"]:
                        st.code(str(step["tool_input"]), language="python")
                    st.json(step["tool_result"])

# --- Chat input box ---
user_question = st.chat_input("e.g. Which customer has spent the most money?")

if user_question:
    # Show the user's message immediately
    with st.chat_message("user"):
        st.write(user_question)
    st.session_state.messages.append({"role": "user", "content": user_question})

    # Run the agent and show a spinner while it thinks/calls tools
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            trace = []
            try:
                answer = ask_agent(user_question, verbose=False, trace=trace)
            except Exception as e:
                answer = f"Something went wrong: {e}"

        st.write(answer)

        if trace:
            with st.expander("🔍 See how the agent got this answer"):
                for step in trace:
                    st.markdown(f"**Called `{step['tool_name']}`**")
                    if step["tool_input"]:
                        st.code(str(step["tool_input"]), language="python")
                    st.json(step["tool_result"])

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "trace": trace,
    })

# --- Sidebar: quick example questions + reset button ---
with st.sidebar:
    st.subheader("Try asking:")
    st.markdown(
        "- Which customer has spent the most money?\n"
        "- What products are in the Fitness category?\n"
        "- How many orders did Rohit Sharma place?\n"
        "- What's the total revenue so far?"
    )
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
