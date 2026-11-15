import os
from datetime import date

import streamlit as st
from google import genai
from google.genai import types

MODEL_NAME = "gemini-3.5-flash-lite"
LOGO_FILE = "logo.png"

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
    "For questions about current events, current office holders, "
    "news, prices or anything that may have changed recently, "
    "use Google Search and trust the search results over your own memory. "
    "The user may attach PDF files, images or voice messages. "
    "Read them carefully and answer based on them. "
    "Always reply in the same language and script as the user's message. "
    "If the user writes in Urdu script, reply in Urdu script. "
    "If the user writes Urdu in Roman letters, reply in Roman Urdu. "
    "If the user writes in English, reply only in English. "
    "Keep answers simple and polite."
)

if "chat" not in st.session_state:
    client = genai.Client(api_key=st.secrets["API_KEY"])
    st.session_state.chat = client.chats.create(
        model=MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction=system_text,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    st.session_state.messages = []


def show_message(role, text):
    with st.chat_message(role):
        if role == "user":
            safe_text = text.replace("]", "\\]")
            st.markdown(":green[" + safe_text + "]")
        else:
            st.markdown(text)


for message in st.session_state.messages:
    show_message(message["role"], message["text"])

prompt = st.chat_input(
    "Type your question",
    accept_file="multiple",
    file_type=["pdf", "png", "jpg", "jpeg"],
    accept_audio=True,
)

if prompt:
    parts = []
    shown_text = prompt.text or ""

    if prompt.text:
        parts.append(prompt.text)

    for uploaded in prompt.files:
        parts.append(
            types.Part.from_bytes(
                data=uploaded.getvalue(),
                mime_type=uploaded.type,
            )
        )
        shown_text = shown_text + "\n\n📎 " + uploaded.name

    if prompt.audio:
        parts.append(
            types.Part.from_bytes(
                data=prompt.audio.getvalue(),
                mime_type="audio/wav",
            )
        )
        shown_text = shown_text + "\n\n🎤 Voice message"

    if not prompt.text:
        parts.append("Please respond to the attached file or voice message.")

    st.session_state.messages.append({"role": "user", "text": shown_text})
    show_message("user", shown_text)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = st.session_state.chat.send_message(parts)
                answer = response.text
            except Exception as error:
                answer = "Error: " + str(error)
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "text": answer})
