from datetime import date
import io
import os

from openai import OpenAI
from pypdf import PdfReader
import streamlit as st

MODEL_NAME = "openai/gpt-oss-120b"
AUDIO_MODEL = "whisper-large-v3-turbo"
LOGO_FILE = "logo.png"
MAX_FILE_CHARS = 4000
MAX_HISTORY = 8

st.set_page_config(page_title="Quantum AI", page_icon="🤖")

col_logo, col_name = st.columns([1, 6])
with col_logo:
    if os.path.exists(LOGO_FILE):
        st.image(LOGO_FILE, width=70)
with col_name:
    st.title("Quantum AI")

today = date.today().strftime("%A, %d %B %Y")

system_text = (
    "You are a friendly AI chatbot named Quantum AI. "
    "Your name is Quantum AI. If anyone asks your name, always say your name is Quantum AI. "
    "Your inventor and creator is Muhammad Umer. "
    "He built you himself on his laptop using Python and VS Code. "
    "If anyone asks who made you or who invented you, "
    "always answer that Muhammad Umer created you. "
    "Today's date is " + today + ". "
    "The user may attach PDF or text files and voice messages. "
    "Their text is included in the message, so read it and answer from it. "
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

if "messages" not in st.session_state:
    st.session_state.messages = []


def show_message(role, text):
    with st.chat_message(role):
        if role == "user":
            for line in text.split("\n"):
                if line.strip():
                    safe_line = line.replace("]", "\\]")
                    st.markdown(":green[" + safe_line + "]")
        else:
            st.markdown(text)


def read_file(uploaded):
    data = uploaded.getvalue()
    if uploaded.name.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
            if len(text) > MAX_FILE_CHARS:
                break
    else:
        text = data.decode("utf-8", errors="ignore")
    return text[:MAX_FILE_CHARS]


for message in st.session_state.messages:
    show_message(message["role"], message["shown"])

prompt = st.chat_input(
    "Type your question",
    accept_file="multiple",
    file_type=["pdf", "txt"],
    accept_audio=True,
)

if prompt:
    typed = prompt.text or ""
    content = typed
    shown = typed

    for uploaded in prompt.files:
        try:
            file_text = read_file(uploaded)
        except Exception:
            file_text = ""
        if file_text.strip():
            content += "\n\n[Attached file: " + uploaded.name + "]\n" + file_text
        else:
            content += "\n\n[Attached file: " + uploaded.name + " - no readable text]"
        shown += "\n\n📎 " + uploaded.name

    if prompt.audio:
        try:
            transcript = client.audio.transcriptions.create(
                model=AUDIO_MODEL,
                file=("voice.wav", prompt.audio.getvalue()),
            )
            content += "\n\n" + transcript.text
            shown += "\n\n🎤 " + transcript.text
        except Exception as error:
            st.error("Voice error: " + str(error))

    if not content.strip():
        st.stop()

    if not typed.strip() and prompt.files:
        content = "Please read the attached file and summarize it.\n" + content

    st.session_state.messages.append(
        {"role": "user", "content": content, "shown": shown}
    )
    show_message("user", shown)

    recent = st.session_state.messages[-MAX_HISTORY:]
    history = []
    for i, m in enumerate(recent):
        is_last = i == len(recent) - 1
        text = m["content"] if is_last else m["shown"]
        history.append({"role": m["role"], "content": text})
    if history and history[0]["role"] == "assistant":
        history = history[1:]

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "system", "content": system_text}] + history,
                )
                answer = response.choices[0].message.content
                st.markdown(answer)
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer, "shown": answer}
                )
            except Exception as error:
                st.session_state.messages.pop()
                st.error("Error: " + str(error))
