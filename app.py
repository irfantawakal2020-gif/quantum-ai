import base64
from datetime import date
import os

from openai import OpenAI
import streamlit as st

MODEL_NAME = "openai/gpt-oss-120b"
AUDIO_MODEL = "whisper-large-v3"
LOGO_FILE = "logo.png"
MAX_HISTORY = 12

ALLOWED_LANGS = ["english", "urdu", "hindi"]
LANG_CODES = {"English": "en", "اردو": "ur"}
HINTS = {
    "English": "This is a clear English sentence.",
    "اردو": "یہ ایک صاف اردو جملہ ہے۔",
    "Auto": "Hello, how are you? آپ کیسے ہیں؟",
}

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

mic_choice = st.radio(
    "🎤 Mic language",
    ["Auto", "English", "اردو"],
    horizontal=True,
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
    "Reply in the same language and script that the user's message is written in. "
    "Rule 1: If the user writes in English, reply in pure English only, "
    "with no Urdu or Hindi words. "
    "Rule 2: If the user writes in Urdu script, reply only in Urdu script "
    "(Nastaliq style Urdu text). "
    "Rule 3: If the user writes Urdu in Roman letters (Roman Urdu), "
    "reply only in Roman Urdu. "
    "Rule 4: If the user writes in Hindi or Devanagari script, "
    "reply in Urdu script and never use Devanagari. "
    "Never mix scripts in one reply. "
    "Never reply in any language other than English, Urdu or Roman Urdu. "
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


def has_devanagari(text):
    for ch in text:
        if "\u0900" <= ch <= "\u097F":
            return True
    return False


def to_urdu_script(text):
    try:
        result = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Convert the given Hindi (Devanagari) text into Urdu script, "
                        "keeping the same words and meaning. "
                        "Output only the Urdu text and nothing else."
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        converted = (result.choices[0].message.content or "").strip()
        return converted if converted else text
    except Exception:
        return text


def transcribe(audio_bytes):
    options = {}
    code = LANG_CODES.get(mic_choice)
    if code:
        options["language"] = code
    result = client.audio.transcriptions.create(
        model=AUDIO_MODEL,
        file=("voice.wav", audio_bytes),
        response_format="verbose_json",
        temperature=0,
        prompt=HINTS.get(mic_choice, HINTS["Auto"]),
        **options,
    )
    detected = (getattr(result, "language", "") or "").lower()
    text = (result.text or "").strip()
    if not code and detected and detected not in ALLOWED_LANGS:
        return None
    return text


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

prompt = st.chat_input("Type your question", accept_audio=True)

if prompt:
    user_text = prompt.text or ""

    if prompt.audio:
        try:
            spoken = transcribe(prompt.audio.getvalue())
            if spoken is None:
                st.warning(
                    "آواز کی زبان پہچانی نہیں گئی۔ اوپر Mic language میں "
                    "English یا اردو چن کر دوبارہ بولیں۔"
                )
            elif spoken:
                if has_devanagari(spoken):
                    spoken = to_urdu_script(spoken)
                user_text = (user_text + "\n" + spoken).strip()
        except Exception as error:
            st.error("Voice error: " + str(error))

    if not user_text.strip():
        st.stop()

    st.session_state.messages.append({"role": "user", "content": user_text})
    show_message("user", user_text)

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
