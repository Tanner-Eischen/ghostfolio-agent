"""Streamlit frontend for Ghostfolio Agent."""

import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Ghostfolio Agent",
    page_icon="ghost",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Title
st.title("Ghostfolio Agent")
st.markdown("AI-powered portfolio assistant for Ghostfolio")

# Sidebar
with st.sidebar:
    st.header("Portfolio Summary")

    # TODO: Add portfolio summary (Task #14)
    st.metric("Total Value", "$---")
    st.metric("YTD Performance", "---%")

    st.divider()

    st.header("Quick Actions")
    if st.button("Analyze Portfolio"):
        st.session_state["query"] = "Analyze my portfolio"

    if st.button("Assess Risk"):
        st.session_state["query"] = "What's my portfolio risk?"

    if st.button("Check Compliance"):
        st.session_state["query"] = "Check my recent transactions for compliance"

    st.divider()

    st.header("Settings")
    st.toggle("Dark Mode", value=True)

# Main chat interface
st.header("Chat with your Portfolio")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask about your portfolio..."):
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # TODO: Implement actual agent call (Task #14)
    with st.chat_message("assistant"):
        st.info("Agent not yet connected. Complete Task #14 to enable chat.")
        response = "This is a placeholder response. The agent will be connected in Task #14."
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

# Footer
st.divider()
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        Ghostfolio Agent v0.1.0 | Powered by Claude 3.5 Sonnet
    </div>
    """,
    unsafe_allow_html=True,
)
