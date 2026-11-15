import html
import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="Quantum AI", page_icon="🤖")
st.title("Quantum AI")

# The API key is read from Streamlit Secrets (never written in the code)
API_KEY = st.secrets["API_KEY"]

system_text = (
"You are a friendly AI chatbot named Quantum AI. " "Your name is Quantum AI. If anyone asks your name, always say your name is Quantum AI. " "Your inventor and creator is Muhammad Umer. " "He built you himself on his laptop using Python and VS Code. " "If anyone asks who made you or who invented you, " "always answer that Muhammad Umer created you. " "Always reply in the same language and script as the user's message. " "If the user writes in Urdu script, reply in Urdu script. " "If the user writes Urdu in Roman letters, reply in Roman Urdu. " "If the user writes in English, reply only in English. "Keep answers simple and polite." )


def user_text(text):
    # Shows the user's message in green
    st.markdown(
        f"<span style='color:#22c55e'>{html.escape(text)}</span>",
        unsafe_allow_html=True,
    )


# Create the chat only once per visitor
if "chat" not in st.session_state:
    st.session_state.client = genai.Client(api_key=API_KEY)  # CHANGED
    st.session_state.chat = st.session_state.client.chats.create(  # CHANGED
        model="gemini-3.5-flash-lite",
        config=types.GenerateContentConfig(
            system_instruction=system_text,
            
        ),
    )
    st.session_state.messages = []

# Show old messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            user_text(msg["text"])
        else:
            st.write(msg["text"])

# Input box
user_input = st.chat_input("Type your question")

if user_input:
    st.session_state.messages.append({"role": "user", "text": user_input})
    with st.chat_message("user"):
        user_text(user_input)

    with st.chat_message("assistant"):
        try:
            response = st.session_state.chat.send_message(user_input)
            answer = response.text
        except Exception as e:
            answer = "Something went wrong. Please try again later."
            st.caption(str(e))
        st.write(answer)

    st.session_state.messages.append({"role": "assistant", "text": answer})
