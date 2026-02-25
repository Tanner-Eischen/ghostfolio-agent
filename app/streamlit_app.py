"""Streamlit frontend for Ghostfolio Agent.

MVP frontend providing:
- Natural language chat interface
- Real-time confidence scoring
- Tool call visualization
- Verification status display
- Escalation warnings
- Session management

Task #14: Build Streamlit MVP Frontend

This frontend connects to the FastAPI backend via HTTP.
Run the backend with: python -m src.api.routes
Or: uvicorn src.api.routes:app --reload
"""

import os
import sys
from pathlib import Path
import uuid
from typing import Any

import httpx
import streamlit as st

# Add project root to Python path for src module imports
# This allows the app to be run from any directory
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Configure page before any other Streamlit commands
st.set_page_config(
    page_title="Ghostfolio Agent",
    page_icon="ghost",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Backend API configuration
# Priority: BACKEND_URL env var > default localhost
# For Railway: Set BACKEND_URL in environment
# For local dev: Uses localhost:8001
API_BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")

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
    if "backend_healthy" not in st.session_state:
        st.session_state.backend_healthy = False
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
    if "page" not in st.session_state:
        st.session_state.page = "Chat"
    if "eval_report" not in st.session_state:
        st.session_state.eval_report = None


def check_backend_health() -> tuple[bool, dict[str, Any] | None]:
    """Check if the FastAPI backend is healthy.

    Returns:
        Tuple of (is_healthy, health_data)
    """
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{API_BASE_URL}/health")
            if response.status_code == 200:
                try:
                    return True, response.json()
                except (ValueError, KeyError):
                    # JSON parsing failed - backend returned invalid response
                    return True, {"status": "ok", "warning": "Invalid health response format"}
            # Non-200 status - backend is unhealthy
            return False, {"error": f"Backend returned status {response.status_code}"}
    except httpx.ConnectError:
        # Connection refused - backend not running
        return False, {"error": "Connection refused - backend not running"}
    except httpx.TimeoutException:
        # Request timed out - backend may be overloaded
        return False, {"error": "Health check timed out - backend may be overloaded"}
    except httpx.InvalidURL:
        # Invalid URL configuration
        return False, {"error": f"Invalid backend URL: {API_BASE_URL}"}
    except Exception:
        # Catch-all for unexpected errors - don't expose internal details
        return False, {"error": "Unable to reach backend server"}


def send_chat_message(message: str, session_id: str) -> dict[str, Any]:
    """Send a chat message to the FastAPI backend.

    Args:
        message: User's message
        session_id: Session identifier

    Returns:
        Response dict with message, confidence, tool_calls, etc.
    """
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{API_BASE_URL}/chat",
                json={
                    "message": message,
                    "session_id": session_id,
                },
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                except (ValueError, KeyError):
                    return {
                        "message": "The backend returned an invalid response. Please try again.",
                        "confidence": 0.0,
                        "confidence_level": "VERY_LOW",
                        "tool_calls": [],
                        "verification_passed": False,
                        "requires_escalation": True,
                        "escalation_triggers": ["Invalid JSON response from backend"],
                        "metadata": {"error": "Invalid response format"},
                    }

                return {
                    "message": data.get("response", "No response received"),
                    "confidence": data.get("confidence", 0),
                    "confidence_level": data.get("confidence_level", "VERY_LOW"),
                    "tool_calls": data.get("tool_calls", []),
                    "session_id": data.get("session_id", session_id),
                    "verification_passed": data.get("verification_passed", True),
                    "requires_escalation": data.get("requires_escalation", False),
                    "escalation_triggers": [],
                    "metadata": {
                        "processing_time_ms": data.get("processing_time_ms", 0),
                        "tools_used": len(data.get("tool_calls", [])),
                    },
                }
            else:
                # Handle non-200 status codes
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", f"Server returned status {response.status_code}")
                except (ValueError, KeyError):
                    error_detail = f"Server returned status {response.status_code}"

                # Provide user-friendly messages based on status code
                if response.status_code == 401:
                    user_message = "Authentication required. Please check your API credentials."
                elif response.status_code == 403:
                    user_message = "Access denied. You don't have permission to perform this action."
                elif response.status_code == 404:
                    user_message = "The requested resource was not found."
                elif response.status_code == 429:
                    user_message = "Too many requests. Please wait a moment and try again."
                elif response.status_code >= 500:
                    user_message = "The backend server encountered an error. Please try again later."
                else:
                    user_message = f"Request failed: {error_detail}"

                return {
                    "message": user_message,
                    "confidence": 0.0,
                    "confidence_level": "VERY_LOW",
                    "tool_calls": [],
                    "verification_passed": False,
                    "requires_escalation": True,
                    "escalation_triggers": [f"HTTP {response.status_code}"],
                    "metadata": {"error": error_detail},
                }

    except httpx.ConnectError:
        return {
            "message": "Cannot connect to the backend server. Please ensure the FastAPI server is running.",
            "confidence": 0.0,
            "confidence_level": "VERY_LOW",
            "tool_calls": [],
            "verification_passed": False,
            "requires_escalation": True,
            "escalation_triggers": ["Connection refused - backend not running"],
            "metadata": {"error": "Connection refused"},
        }
    except httpx.TimeoutException:
        return {
            "message": "The request timed out. This can happen with complex queries. Please try again or simplify your question.",
            "confidence": 0.0,
            "confidence_level": "VERY_LOW",
            "tool_calls": [],
            "verification_passed": False,
            "requires_escalation": True,
            "escalation_triggers": ["Request timeout after 60 seconds"],
            "metadata": {"error": "Timeout"},
        }
    except httpx.InvalidURL:
        return {
            "message": "The backend URL configuration is invalid. Please check your environment settings.",
            "confidence": 0.0,
            "confidence_level": "VERY_LOW",
            "tool_calls": [],
            "verification_passed": False,
            "requires_escalation": True,
            "escalation_triggers": ["Invalid backend URL"],
            "metadata": {"error": "Invalid URL"},
        }
    except httpx.RequestError:
        return {
            "message": "A network error occurred while communicating with the backend. Please check your connection.",
            "confidence": 0.0,
            "confidence_level": "VERY_LOW",
            "tool_calls": [],
            "verification_passed": False,
            "requires_escalation": True,
            "escalation_triggers": ["Network error"],
            "metadata": {"error": "Network error"},
        }
    except Exception:
        # Catch-all for unexpected errors - don't expose internal details
        return {
            "message": "An unexpected error occurred. Please try again. If the problem persists, contact support.",
            "confidence": 0.0,
            "confidence_level": "VERY_LOW",
            "tool_calls": [],
            "verification_passed": False,
            "requires_escalation": True,
            "escalation_triggers": ["Unexpected error"],
            "metadata": {"error": "Unexpected error"},
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
    """Render tool calls in a compact format with badges."""
    if not tool_calls:
        return

    st.markdown("**Tools Used:**")
    tool_names = [tc.get("tool", tc.get("name", "unknown")) for tc in tool_calls]

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


def render_tool_calls_collapsible(tool_calls: list[dict]) -> None:
    """Render tool calls in collapsible sections with full details.

    Each tool call is shown in an expandable expander with:
    - Tool name
    - Input parameters (collapsible)
    - Output (if available)

    Args:
        tool_calls: List of tool call dicts with 'tool' and 'input' keys
    """
    if not tool_calls:
        return

    with st.expander(f"🔧 Tool Calls ({len(tool_calls)})", expanded=False):
        for i, tc in enumerate(tool_calls, 1):
            tool_name = tc.get("tool", tc.get("name", "unknown"))
            tool_input = tc.get("input", {})
            tool_output = tc.get("output", None)

            # Tool header with colored badge
            colors = {
                "portfolio_analysis": "#3498db",
                "risk_assessment": "#e74c3c",
                "transaction_categorize": "#9b59b6",
                "market_data_lookup": "#2ecc71",
                "compliance_check": "#f39c12",
            }
            color = colors.get(tool_name, "#95a5a6")

            st.markdown(
                f'<span style="background: {color}; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 500;">{i}. {tool_name}</span>',
                unsafe_allow_html=True,
            )

            # Input section (collapsible)
            if tool_input:
                with st.expander("📥 Input", expanded=False):
                    st.json(tool_input)

            # Output section (collapsible)
            if tool_output:
                with st.expander("📤 Output", expanded=False):
                    if isinstance(tool_output, dict):
                        st.json(tool_output)
                    else:
                        st.markdown(f"```\n{tool_output}\n```")

            st.markdown("")  # Spacing between tools


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

        # Page selector
        st.session_state.page = st.radio(
            "View",
            ["Chat", "Evaluations"],
            index=0 if st.session_state.page == "Chat" else 1,
            label_visibility="collapsed",
        )
        st.divider()

        # Backend Status
        st.subheader("Backend Status")
        is_healthy, health_data = check_backend_health()
        st.session_state.backend_healthy = is_healthy

        if is_healthy:
            st.success("Connected")
            with st.expander("Details", expanded=False):
                st.json(health_data or {})
        else:
            st.error("Disconnected")
            # Show the specific error reason if available
            if health_data and "error" in health_data:
                st.caption(health_data["error"])
            # Provide helpful guidance
            st.caption("To start the backend:")
            st.code("uvicorn src.api.routes:app --reload", language="bash")
            st.caption("Or from the project root:")
            st.code("python -m src.api.routes", language="bash")

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


def render_chat_message(message: dict, use_collapsible_tools: bool = True) -> None:
    """Render a single chat message.

    Args:
        message: Message dict with role, content, and optional metadata
        use_collapsible_tools: If True, render tool calls in collapsible sections
    """
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

            # Tool calls - use collapsible display by default
            if meta.get("tool_calls"):
                if use_collapsible_tools:
                    render_tool_calls_collapsible(meta["tool_calls"])
                else:
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

    # Check backend health first
    if not st.session_state.backend_healthy:
        with st.chat_message("assistant"):
            st.error("Backend Unavailable")
            st.markdown(
                """
                The backend server is not responding. To fix this:

                1. **Start the backend server:**
                   ```
                   uvicorn src.api.routes:app --reload
                   ```
                2. **Or from the project root:**
                   ```
                   python -m src.api.routes
                   ```
                3. **Check the backend URL:** Make sure `BACKEND_URL` environment variable is set correctly (default: `http://localhost:8001`)
                """
            )
        return

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response = send_chat_message(
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

        # Render tool calls in collapsible sections
        tool_calls = response.get("tool_calls", [])
        if tool_calls:
            render_tool_calls_collapsible(tool_calls)

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


def run_mvp_evals() -> dict[str, Any] | None:
    """Run MVP evals via subprocess and return report dict."""
    import subprocess

    results_dir = _project_root / "evals" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / "eval_report_streamlit.json"

    try:
        subprocess.run(
            [
                "python",
                str(_project_root / "evals" / "run_evals.py"),
                "--category",
                "mvp",
                "--save",
                "--output",
                str(out_path),
            ],
            cwd=str(_project_root),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if out_path.exists():
            with open(out_path) as f:
                import json
                return json.load(f)
    except Exception as e:
        st.error(f"Eval run failed: {e}")
    return None


def render_eval_report(report: dict[str, Any]) -> None:
    """Render eval report with per-case and per-criterion pass/fail plus tool visualization."""
    summary = report.get("summary", {})
    st.subheader("MVP Evaluation Report")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total", summary.get("total_tests", 0))
    with col2:
        st.metric("Passed", summary.get("passed", 0))
    with col3:
        st.metric("Pass Rate", f"{summary.get('pass_rate', 0):.1f}%")

    st.divider()

    results = report.get("results", [])
    for r in results:
        case_id = r.get("id", "?")
        passed = r.get("passed", False)
        input_text = r.get("input", "")[:60] + ("..." if len(r.get("input", "")) > 60 else "")
        tool_calls = r.get("tool_calls", [])

        status = "PASS" if passed else "FAIL"
        status_color = "#28a745" if passed else "#dc3545"
        with st.expander(f"[{status}] {case_id}: {input_text}", expanded=not passed):
            st.markdown(f"**Input:** {r.get('input', '')}")
            st.markdown(f"**Overall:** {status}")

            # Tool call visualization
            if tool_calls:
                st.markdown("**Tools Called:**")
                colors = {
                    "portfolio_analysis": "#3498db",
                    "risk_assessment": "#e74c3c",
                    "market_data_lookup": "#2ecc71",
                }
                badges = ""
                for t in tool_calls:
                    color = colors.get(t, "#95a5a6")
                    badges += f'<span style="background:{color};color:white;padding:2px 8px;border-radius:12px;font-size:12px;margin-right:4px;">{t}</span>'
                st.markdown(badges, unsafe_allow_html=True)

            # Full JSON payloads for inspection/debugging
            tool_call_details = r.get("tool_call_details", [])
            if tool_call_details:
                with st.expander("Tool call JSON", expanded=False):
                    st.json(tool_call_details)

            tool_outputs = r.get("tool_outputs", [])
            if tool_outputs:
                with st.expander("Tool output JSON", expanded=False):
                    st.json(tool_outputs)

            # Per-criterion pass/fail
            criteria = r.get("criteria_results", [])
            if criteria:
                st.markdown("**Criteria:**")
                for c in criteria:
                    c_status = "PASS" if c.get("passed") else "FAIL"
                    c_color = "#28a745" if c.get("passed") else "#dc3545"
                    st.markdown(f"- {c.get('id', '?')}: {c.get('description', '')} — **{c_status}**")
                    if not c.get("passed") and c.get("expected"):
                        st.caption(f"  Expected: {c.get('expected')}, Got: {c.get('actual')}")

            if r.get("response"):
                with st.expander("Response preview", expanded=False):
                    st.text(r["response"][:500] + ("..." if len(r.get("response", "")) > 500 else ""))


def render_eval_view() -> None:
    """Render the MVP Evaluations view."""
    st.header("MVP Evaluations")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Run MVP Evals", type="primary"):
            with st.spinner("Running evals (this may take 1-2 minutes)..."):
                report = run_mvp_evals()
                if report:
                    st.session_state.eval_report = report
                    st.rerun()

    with col2:
        uploaded = st.file_uploader("Or load report JSON", type=["json"])
        if uploaded:
            import json
            try:
                report = json.load(uploaded)
                st.session_state.eval_report = report
                st.rerun()
            except json.JSONDecodeError:
                st.error("Invalid JSON file")

    if st.session_state.eval_report:
        st.divider()
        render_eval_report(st.session_state.eval_report)
    else:
        st.info("Run MVP evals or load a report to see results.")


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

    if st.session_state.page == "Evaluations":
        render_eval_view()
        return

    # Main content area (Chat)
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
