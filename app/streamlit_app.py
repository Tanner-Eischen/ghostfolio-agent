"""Streamlit frontend for Ghostfolio Agent.

MVP frontend providing:
- Natural language chat interface
- Real-time confidence scoring
- Tool call visualization
- Verification status display
- Escalation warnings
- Session management

Task #14: Build Streamlit MVP Frontend
"""

import asyncio
import uuid
from typing import Any

import streamlit as st

# Configure page before any other Streamlit commands
st.set_page_config(
    page_title="Ghostfolio Agent",
    page_icon="ghost",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Constants
CONFIDENCE_THRESHOLDS = {
    "VERY_HIGH": {"min": 90, "color": "#28a745", "emoji": "excellent"},
    "HIGH": {"min": 80, "color": "#5cb85c", "emoji": "good"},
    "MEDIUM": {"min": 70, "color": "#ffc107", "emoji": "moderate"},
    "LOW": {"min": 50, "color": "#fd7e14", "emoji": "low"},
    "VERY_LOW": {"min": 0, "color": "#dc3545", "emoji": "very-low"},
}


def get_confidence_style(score: float) -> dict[str, str]:
    """Get color and emoji for confidence score."""
    if score >= 90:
        return CONFIDENCE_THRESHOLDS["VERY_HIGH"]
    elif score >= 80:
        return CONFIDENCE_THRESHOLDS["HIGH"]
    elif score >= 70:
        return CONFIDENCE_THRESHOLDS["MEDIUM"]
    elif score >= 50:
        return CONFIDENCE_THRESHOLDS["LOW"]
    else:
        return CONFIDENCE_THRESHOLDS["VERY_LOW"]


def init_session_state() -> None:
    """Initialize all session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "last_response" not in st.session_state:
        st.session_state.last_response = None
    if "show_debug" not in st.session_state:
        st.session_state.show_debug = False
    if "total_queries" not in st.session_state:
        st.session_state.total_queries = 0
    if "portfolio_value" not in st.session_state:
        st.session_state.portfolio_value = None
    if "portfolio_performance" not in st.session_state:
        st.session_state.portfolio_performance = None


def get_agent():
    """Get or initialize the GhostfolioAgent lazily."""
    if st.session_state.agent is None:
        with st.spinner("Initializing agent..."):
            try:
                from src.agent import GhostfolioAgent

                st.session_state.agent = GhostfolioAgent(
                    model="gpt-4o-mini",
                    temperature=0.0,
                    use_verification=True,
                    verification_strict_mode=False,
                    enable_tracing=True,
                )
            except Exception as e:
                st.error(f"Failed to initialize agent: {e}")
                return None
    return st.session_state.agent


async def chat_with_agent(agent, message: str, session_id: str) -> dict[str, Any]:
    """Async wrapper for agent chat."""
    return await agent.chat_with_context(message, session_id=session_id)


def run_async_chat(agent, message: str, session_id: str) -> dict[str, Any]:
    """Run async chat in sync context."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(chat_with_agent(agent, message, session_id))
        loop.close()
        return result
    except Exception as e:
        return {
            "message": f"Error: {str(e)}",
            "confidence": 0.0,
            "confidence_level": "VERY_LOW",
            "tool_calls": [],
            "verification_passed": False,
            "requires_escalation": True,
            "escalation_triggers": [str(e)],
            "metadata": {"error": str(e)},
        }


def render_confidence_indicator(score: float, level: str) -> None:
    """Render confidence score with visual indicator."""
    style = get_confidence_style(score)
    color = style["color"]

    # Create progress bar with color
    st.markdown(
        f"""
        <div style="margin-bottom: 5px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 500;">Confidence</span>
                <span style="color: {color}; font-weight: 600;">{score:.1f}% ({level})</span>
            </div>
            <div style="background: #e9ecef; border-radius: 4px; height: 8px; margin-top: 4px;">
                <div style="background: {color}; width: {min(score, 100)}%; height: 100%; border-radius: 4px; transition: width 0.3s;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_tool_calls(tool_calls: list[dict]) -> None:
    """Render tool calls in a compact format."""
    if not tool_calls:
        return

    st.markdown("**Tools Used:**")
    tool_names = [tc.get("tool", "unknown") for tc in tool_calls]

    # Create badges for each tool
    badges_html = ""
    colors = {
        "portfolio_analysis": "#3498db",
        "risk_assessment": "#e74c3c",
        "transaction_categorize": "#9b59b6",
        "market_data_lookup": "#2ecc71",
        "compliance_check": "#f39c12",
    }

    for tool in tool_names:
        color = colors.get(tool, "#95a5a6")
        badges_html += f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-right: 4px;">{tool}</span>'

    st.markdown(badges_html, unsafe_allow_html=True)


def render_escalation_warning(triggers: list[str]) -> None:
    """Render escalation warning if needed."""
    if not triggers:
        return

    st.warning("Review Recommended")
    with st.expander("View Details", expanded=False):
        for trigger in triggers:
            st.markdown(f"- {trigger}")


def render_response_metadata(response: dict[str, Any]) -> None:
    """Render response metadata in a collapsible section."""
    with st.expander("Response Details", expanded=st.session_state.show_debug):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Processing Time",
                f"{response.get('metadata', {}).get('processing_time_ms', 0):.0f}ms",
            )

        with col2:
            st.metric(
                "Tools Called",
                response.get("metadata", {}).get("tools_used", 0),
            )

        with col3:
            verification = "Passed" if response.get("verification_passed", False) else "Failed"
            st.metric("Verification", verification)

        # Escalation info
        if response.get("requires_escalation", False):
            st.markdown("---")
            render_escalation_warning(response.get("escalation_triggers", []))


def render_sidebar() -> None:
    """Render the sidebar with portfolio summary and controls."""
    with st.sidebar:
        # Logo and title
        st.markdown(
            """
            <div style="text-align: center; padding: 10px 0;">
                <h1 style="margin: 0; color: #7c3aed;">Ghostfolio Agent</h1>
                <p style="color: gray; font-size: 12px;">AI Portfolio Assistant</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

        # Portfolio Summary Section
        st.subheader("Portfolio Summary")

        # Try to get portfolio data
        if st.session_state.portfolio_value:
            st.metric(
                "Total Value",
                f"${st.session_state.portfolio_value:,.2f}",
            )
            if st.session_state.portfolio_performance:
                perf = st.session_state.portfolio_performance
                delta_color = "normal" if perf >= 0 else "inverse"
                st.metric(
                    "Performance",
                    f"{perf:+.2f}%",
                    delta_color=delta_color,
                )
        else:
            st.metric("Total Value", "$---")
            st.metric("Performance", "---%")
            st.caption("Ask about your portfolio to see data")

        st.divider()

        # Quick Actions
        st.subheader("Quick Actions")

        if st.button("Analyze Portfolio", use_container_width=True):
            st.session_state.query = "Analyze my portfolio and show me the total value and allocation"

        if st.button("Assess Risk", use_container_width=True):
            st.session_state.query = "What's my portfolio risk level? Am I well diversified?"

        if st.button("Check Compliance", use_container_width=True):
            st.session_state.query = "Check my recent transactions for compliance issues"

        if st.button("Market Lookup", use_container_width=True):
            st.session_state.query = "What are the current prices of AAPL, MSFT, and VTI?"

        if st.button("Categorize Transactions", use_container_width=True):
            st.session_state.query = "Categorize my recent transactions and identify patterns"

        st.divider()

        # Session Info
        st.subheader("Session")
        st.caption(f"ID: {st.session_state.session_id[:8]}...")
        st.metric("Queries", st.session_state.total_queries)

        if st.button("New Session", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.total_queries = 0
            st.session_state.portfolio_value = None
            st.session_state.portfolio_performance = None
            st.rerun()

        st.divider()

        # Settings
        st.subheader("Settings")
        st.session_state.show_debug = st.toggle("Show Debug Info", value=False)

        st.divider()

        # About
        st.markdown(
            """
            <div style="font-size: 12px; color: gray;">
                <p><strong>Powered by:</strong></p>
                <ul style="margin: 0; padding-left: 16px;">
                    <li>Claude 3.5 Sonnet / GPT-4o</li>
                    <li>LangChain + LangGraph</li>
                    <li>LangSmith Observability</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_chat_message(message: dict) -> None:
    """Render a single chat message."""
    role = message["role"]
    content = message["content"]

    with st.chat_message(role):
        st.markdown(content)

        # Show metadata for assistant messages
        if role == "assistant" and "metadata" in message:
            meta = message.get("metadata", {})

            # Confidence indicator
            if "confidence" in meta:
                render_confidence_indicator(
                    meta["confidence"],
                    meta.get("confidence_level", "UNKNOWN"),
                )

            # Tool calls
            if meta.get("tool_calls"):
                render_tool_calls(meta["tool_calls"])

            # Verification status
            if not meta.get("verification_passed", True):
                st.error("Verification Failed")

            # Escalation warning
            if meta.get("requires_escalation", False):
                render_escalation_warning(meta.get("escalation_triggers", []))


def render_chat_interface() -> None:
    """Render the main chat interface."""
    st.header("Chat with your Portfolio")

    # Display all messages
    for message in st.session_state.messages:
        render_chat_message(message)

    # Handle quick action query
    if "query" in st.session_state and st.session_state.query:
        prompt = st.session_state.query
        st.session_state.query = None  # Clear after use
        process_message(prompt)

    # Chat input
    if prompt := st.chat_input("Ask about your portfolio..."):
        process_message(prompt)


def process_message(prompt: str) -> None:
    """Process a user message and get agent response."""
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Get agent response
    agent = get_agent()
    if agent is None:
        return

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response = run_async_chat(
                agent,
                prompt,
                st.session_state.session_id,
            )

        st.session_state.last_response = response
        st.session_state.total_queries += 1

        # Extract and display message
        message = response.get("message", "No response received")
        st.markdown(message)

        # Render confidence
        confidence = response.get("confidence", 0)
        confidence_level = response.get("confidence_level", "VERY_LOW")
        render_confidence_indicator(confidence, confidence_level)

        # Render tool calls
        tool_calls = response.get("tool_calls", [])
        if tool_calls:
            render_tool_calls(tool_calls)

        # Check verification
        if not response.get("verification_passed", True):
            st.error("Response verification failed")

        # Escalation warning
        if response.get("requires_escalation", False):
            render_escalation_warning(response.get("escalation_triggers", []))

        # Debug info
        if st.session_state.show_debug:
            render_response_metadata(response)

        # Store message with metadata
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": message,
                "metadata": {
                    "confidence": confidence,
                    "confidence_level": confidence_level,
                    "tool_calls": tool_calls,
                    "verification_passed": response.get("verification_passed", True),
                    "requires_escalation": response.get("requires_escalation", False),
                    "escalation_triggers": response.get("escalation_triggers", []),
                    "processing_time_ms": response.get("metadata", {}).get("processing_time_ms", 0),
                },
            }
        )

        # Try to extract portfolio value if present
        try_extract_portfolio_data(message, prompt)


def try_extract_portfolio_data(message: str, query: str) -> None:
    """Try to extract portfolio value from response for sidebar display."""
    import re

    # Look for portfolio value patterns
    value_patterns = [
        r"\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
        r"total value of \$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
        r"portfolio (?:is )?(?:worth )?\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
    ]

    for pattern in value_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            try:
                value_str = match.group(1).replace(",", "")
                value = float(value_str)
                if value > 1000:  # Reasonable portfolio value
                    st.session_state.portfolio_value = value
            except (ValueError, IndexError):
                pass

    # Look for performance percentage
    perf_pattern = r"([-+]?\d+(?:\.\d+)?)\s*%"
    match = re.search(perf_pattern, message)
    if match:
        try:
            perf = float(match.group(1))
            if -100 < perf < 1000:  # Reasonable performance
                st.session_state.portfolio_performance = perf
        except ValueError:
            pass


def render_tools_overview() -> None:
    """Render a collapsible section showing available tools."""
    with st.expander("Available Tools", expanded=False):
        tools_info = [
            {
                "name": "portfolio_analysis",
                "icon": "chart-pie",
                "description": "Analyze holdings, allocation, and performance",
                "examples": [
                    "What's my portfolio worth?",
                    "Show me my allocation",
                    "How diversified am I?",
                ],
            },
            {
                "name": "risk_assessment",
                "icon": "shield",
                "description": "Evaluate concentration and diversification risk",
                "examples": [
                    "What's my risk level?",
                    "Am I overexposed to tech?",
                    "Rate my portfolio risk",
                ],
            },
            {
                "name": "transaction_categorize",
                "icon": "tags",
                "description": "Categorize transactions and detect patterns",
                "examples": [
                    "Categorize my trades",
                    "Do I follow DCA?",
                    "Any dividend stocks?",
                ],
            },
            {
                "name": "market_data_lookup",
                "icon": "trending-up",
                "description": "Get current prices for stocks and crypto",
                "examples": [
                    "What's AAPL trading at?",
                    "Bitcoin price?",
                    "Get prices for my holdings",
                ],
            },
            {
                "name": "compliance_check",
                "icon": "check-circle",
                "description": "Check for wash sales and trading rules",
                "examples": [
                    "Check for wash sales",
                    "Am I a pattern day trader?",
                    "Review compliance",
                ],
            },
        ]

        for tool in tools_info:
            st.markdown(f"**{tool['name']}**")
            st.caption(tool["description"])
            st.markdown("")

        st.markdown("---")
        st.markdown(
            """
            <small>
            All responses are verified for accuracy. Confidence scores indicate
            the reliability of the response. Scores below 70% may require review.
            </small>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    """Main application entry point."""
    # Initialize session state
    init_session_state()

    # Render sidebar
    render_sidebar()

    # Main content area
    col1, col2 = st.columns([3, 1])

    with col1:
        # Chat interface
        render_chat_interface()

    with col2:
        # Tools overview and help
        render_tools_overview()

        # Recent activity
        if st.session_state.last_response:
            st.divider()
            st.subheader("Last Response")

            response = st.session_state.last_response
            st.metric(
                "Confidence",
                f"{response.get('confidence', 0):.1f}%",
            )
            st.metric(
                "Time",
                f"{response.get('metadata', {}).get('processing_time_ms', 0):.0f}ms",
            )

    # Footer
    st.divider()
    st.markdown(
        """
        <div style='text-align: center; color: gray; font-size: 12px;'>
            Ghostfolio Agent v0.1.0 |
            <a href="https://github.com/Tanner-Eischen/ghostfolio-agent" target="_blank">GitHub</a> |
            Powered by Claude 3.5 Sonnet
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
