from datetime import date
import os

from openai import OpenAI
import streamlit as st

MODEL_NAME = "grok-2"
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
    "Your name is Quantum AI. If anyone asks your name, always say your name"
    " is Quantum AI. "
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

if "messages" not in st.session_state:
  st.session_state.client = OpenAI(
      api_key=st.secrets["GROK_API_KEY"], base_url="https://api.x.ai/v1"
  )
  st.session_state.messages = [{"role": "system", "content": system_text}]


def show_message(role, text):
  with st.chat_message(role):
    if role == "user":
      for line in text.split("\n"):
        if line.strip():
          safe_line = line.replace("]", "\\]")
          st.markdown(":green[" + safe_line + "]")
    else:
      st.markdown(text)


for message in st.session_state.messages:
  show_message(message["role"], message["content"])

prompt = st.chat_input("Type your question")

if prompt:
  st.session_state.messages.append({"role": "user", "content": prompt})
  show_message("user", prompt)

  with st.chat_message("assistant"):
    with st.spinner("Thinking..."):
      try:
        response = st.session_state.client.chat.completions.create(
            model=MODEL_NAME, messages=st.session_state.messages
        )
        answer = response.choices[0].message.content
      except Exception as error:
        answer = "Error: " + str(error)
    st.markdown(answer)

  st.session_state.messages.append({"role": "assistant", "content": answer})
