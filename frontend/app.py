import os
from pathlib import Path

import httpx
import streamlit as st
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

DEFAULT_BACKEND_URL = "http://127.0.0.1:8001"
BACKEND_URL = os.getenv("AGENT_BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")
REQUEST_TIMEOUT = 120.0

EXAMPLE_PROMPTS = [
    "What's the current weather in Tokyo?",
    "Will it rain in London this weekend?",
    "Compare the temperature in Paris and New York today.",
    "Give me a 5-day forecast for Sydney.",
    "What should I wear in Berlin tomorrow?",
]


class BackendError(Exception):
    """Raised when the agent backend returns an application error."""


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
        detail = payload.get("detail", response.text)
        if isinstance(detail, list):
            return "; ".join(str(item) for item in detail)
        return str(detail)
    except ValueError:
        return response.text or f"HTTP {response.status_code}"


def check_health() -> tuple[bool, str]:
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{BACKEND_URL}/health")
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") == "ok":
                return True, "Backend is healthy"
            return False, f"Unexpected health response: {payload}"
    except httpx.ConnectError:
        return (
            False,
            f"Cannot connect to backend at {BACKEND_URL}. "
            "Start the agent server with `python main.py` in agent-backend/.",
        )
    except httpx.TimeoutException:
        return False, "Backend health check timed out."
    except httpx.HTTPStatusError as exc:
        return False, f"Health check failed: {_extract_error_detail(exc.response)}"
    except Exception as exc:
        return False, f"Health check failed: {exc}"


def send_chat(message: str, history: list[dict[str, str]]) -> str:
    payload = {"message": message, "history": history}
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        response = client.post(f"{BACKEND_URL}/chat", json=payload)

    if response.status_code == 503:
        raise BackendError(_extract_error_detail(response))

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise BackendError(_extract_error_detail(exc.response)) from exc

    data = response.json()
    reply = data.get("response")
    if not isinstance(reply, str):
        raise BackendError("Backend returned an unexpected response format.")
    return reply


def _process_user_message(prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    history = [
        {"role": message["role"], "content": message["content"]}
        for message in st.session_state.messages[:-1]
    ]

    with st.chat_message("assistant"):
        with st.spinner("Fetching weather insights..."):
            try:
                reply = send_chat(prompt, history)
            except httpx.ConnectError:
                st.error(
                    f"Could not connect to the agent backend at `{BACKEND_URL}`. "
                    "Make sure the server is running in `agent-backend/`."
                )
                return
            except httpx.TimeoutException:
                st.error(
                    "The request timed out. The agent may still be working on a "
                    "slow response—try again in a moment."
                )
                return
            except BackendError as exc:
                st.error(str(exc))
                return
            except Exception as exc:
                st.error(f"Unexpected error: {exc}")
                return

        st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})


def main() -> None:
    st.set_page_config(page_title="Weather Agent", page_icon="🌤️")
    st.title("Weather Agent")
    st.caption(
        "Ask natural-language questions about weather anywhere in the world."
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        st.header("Example prompts")
        for index, example in enumerate(EXAMPLE_PROMPTS):
            if st.button(example, key=f"example_{index}", use_container_width=True):
                st.session_state.pending_prompt = example

        st.divider()
        healthy, health_message = check_health()
        if healthy:
            st.success(health_message)
        else:
            st.warning(health_message)

        st.caption(f"Backend: `{BACKEND_URL}`")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    pending_prompt = st.session_state.pop("pending_prompt", None)
    if pending_prompt:
        _process_user_message(pending_prompt)

    if user_prompt := st.chat_input("Ask about the weather..."):
        _process_user_message(user_prompt)


if __name__ == "__main__":
    main()
