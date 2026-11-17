import base64
from datetime import date
import os

from openai import OpenAI
import streamlit as st

MODEL_NAME = "openai/gpt-oss-120b"
LOGO_FILE = "logo.png"
MAX_HISTORY = 12

has_logo = os.path.exists(LOGO_FILE)

st.set_page_config(
    page_title="Quantum AI",
    page_icon=LOGO_FILE if has_logo else "🤖",
)

CSS = """
<style>
.stApp {
    background: radial-gradient(circle at top, #2a1458 0%, #120a28 45%, #0a0616 100%);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { display: none; }
footer { visibility: hidden; }
.block-container { max-width: 760px; padding-top: 2rem; }
.qa-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 1.2rem;
}
.qa-logo {
    width: 68px;
    height: 68px;
    border-radius: 18px;
    box-shadow: 0 0 24px rgba(150, 90, 255, 0.6);
}
.qa-title {
    font-size: 2.3rem;
    font-weight: 800;
    line-height: 1.1;
    background: linear-gradient(90deg, #f1ecff, #b88cff, #7c4dff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.qa-sub { color: #b9a8e6; font-size: 0.95rem; }
.qa-welcome {
    text-align: center;
    color: #cfc2f5;
    padding: 1.2rem;
    margin: 1rem 0;
    border: 1px dashed rgba(160, 110, 255, 0.4);
    border-radius: 16px;
    background: rgba(120, 70, 255, 0.08);
}
[data-testid="stChatMessage"] {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(160, 110, 255, 0.2);
    border-radius: 16px;
    padding: 0.8rem 1rem;
}
[data-testid="stChatInput"] {
    border: 1px solid #7c4dff;
    border-radius: 18px;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def logo_html():
    if not has_logo:
        return ""
    with open(LOGO_FILE, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return '<img class="qa-logo" src="data:image/png;base64,' + data + '">'


st.markdown(
    '<div class="qa-header">'
    + logo_html()
    + '<div><div class="qa-title">Quantum AI</div>'
    + '<div class="qa-sub">Ask me anything</div></div></div>',
    unsafe_allow_html=True,
)

today = date.today().strftime("%A, %d %B %Y")

system_text = (
    "You are a friendly AI chatbot named Quantum AI. "
    "Your name is Quantum AI. If anyone asks your name, always say your name is Quantum AI. "
    "Your inventor and creator is Muhammad Umer. "
    "He built you himself on his laptop using Python and VS Code. "
    "If anyone asks who made you or who invented you, "
    "always answer that Muhammad Umer created you. "
    "Today's date is " + today + ". "
    "Always reply in the same language and script as the user's message. "
    "If the user writes in Urdu script, reply in Urdu script. "
    "If the user writes Urdu in Roman letters, reply in Roman Urdu. "
    "If the user writes in English, reply only in English. "
    "Keep answers simple and polite."
)

API_KEY = st.secrets.get("GROQ_API_KEY") or st.secrets.get("GROK_API_KEY")

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

USER_AVATAR = "🧑‍💻"
BOT_AVATAR = LOGO_FILE if has_logo else "🤖"

if "messages" not in st.session_state:
    st.session_state.messages = []


def show_message(role, text):
    avatar = USER_AVATAR if role == "user" else BOT_AVATAR
    with st.chat_message(role, avatar=avatar):
        if role == "user":
            for line in text.split("\n"):
                if line.strip():
                    safe_line = line.replace("]", "\\]")
                    st.markdown(":green[" + safe_line + "]")
        else:
            st.markdown(text)


if st.session_state.messages:
    if st.button("🗑️ New chat"):
        st.session_state.messages = []
        st.rerun()
else:
    st.markdown(
        '<div class="qa-welcome">👋 Welcome!<br>'
        "آپ اردو، رومن اردو یا انگریزی میں سوال پوچھ سکتے ہیں۔</div>",
        unsafe_allow_html=True,
    )

for message in st.session_state.messages:
    show_message(message["role"], message["content"])

prompt = st.chat_input("Type your question")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    show_message("user", prompt)

    recent = st.session_state.messages[-MAX_HISTORY:]

    with st.chat_message("assistant", avatar=BOT_AVATAR):
        with st.spinner("Thinking..."):
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "system", "content": system_text}] + recent,
                )
                answer = response.choices[0].message.content
                st.markdown(answer)
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer}
                )
            except Exception as error:
                st.session_state.messages.pop()
                st.error("Error: " + str(error))
