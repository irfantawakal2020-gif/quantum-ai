import base64
from datetime import date
import json
import math
import os
import random
import re
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import textwrap
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

from openai import OpenAI
from tavily import TavilyClient
from youtube_transcript_api import YouTubeTranscriptApi
import streamlit as st
import streamlit.components.v1 as components

MODEL_NAME = "openai/gpt-oss-120b"
AUDIO_MODEL = "whisper-large-v3"
SMALL_MODEL = "openai/gpt-oss-20b"
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
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(160, 110, 255, 0.22);
    border-radius: 20px 20px 20px 6px;
    padding: 0.8rem 1rem;
    max-width: 92%;
    margin-right: auto;
}
[data-testid="stChatMessage"]:has(.qa-u) {
    flex-direction: row-reverse;
    width: fit-content;
    max-width: 85%;
    margin-left: auto;
    margin-right: 0;
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.5), rgba(76, 29, 149, 0.4));
    border: 1px solid rgba(167, 139, 250, 0.55);
    border-radius: 20px 20px 6px 20px;
}
[data-testid="stElementContainer"]:has(.qa-u),
.element-container:has(.qa-u) {
    display: none;
}
.katex-display {
    overflow-x: auto;
    overflow-y: hidden;
    padding: 0.3rem 0;
}
.katex { font-size: 1.08em; }
[data-testid="stBottom"],
[data-testid="stBottom"] > div {
    background: transparent !important;
}
[data-testid="stBottomBlockContainer"] {
    padding-bottom: 1.8rem;
}
[data-testid="stChatInput"] {
    border: 1px solid #8b5cf6;
    border-radius: 32px !important;
    box-shadow:
        0 0 10px 2px rgba(109, 40, 217, 0.55),
        0 0 28px 6px rgba(76, 29, 149, 0.45);
    animation: qaGlow 3s ease-in-out infinite;
}
[data-testid="stChatInput"] > div,
[data-testid="stChatInput"] > div > div {
    border-radius: 32px !important;
}
[data-testid="stChatInput"] textarea {
    border-radius: 32px !important;
    padding-left: 1.4rem !important;
}
[data-testid="stChatInputSubmitButton"],
[data-testid="stChatInput"] button {
    border-radius: 50% !important;
    aspect-ratio: 1 / 1;
}
[data-testid="stChatInput"]:focus-within {
    animation: none;
    box-shadow:
        0 0 14px 4px rgba(139, 92, 246, 0.85),
        0 0 44px 12px rgba(91, 33, 182, 0.6);
}
@keyframes qaGlow {
    0%, 100% {
        box-shadow:
            0 0 8px 1px rgba(109, 40, 217, 0.45),
            0 0 22px 4px rgba(76, 29, 149, 0.35);
    }
    50% {
        box-shadow:
            0 0 14px 3px rgba(139, 92, 246, 0.7),
            0 0 38px 9px rgba(91, 33, 182, 0.55);
    }
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

speak_on = st.toggle("🔊 Read answers aloud", value=False)
ai_on = st.toggle(
    "🎙️ AI transcript for videos without captions (uses Supadata credits)",
    value=True,
)

UNLOCK_HTML = r"""
<script>
try {
  const W = window.parent;
  const synth = W.speechSynthesis;
  if (synth && !W.__qaUnlock) {
    W.__qaUnlock = true;
    const unlock = function () {
      try {
        if (synth.speaking || synth.pending) { return; }
        const u = new W.SpeechSynthesisUtterance(" ");
        u.volume = 0;
        synth.speak(u);
      } catch (e) {}
    };
    W.document.addEventListener("click", unlock, true);
    W.document.addEventListener("touchend", unlock, true);
  }
} catch (e) {}
</script>
"""

if speak_on:
    components.html(UNLOCK_HTML, height=0)

today = date.today().strftime("%A, %d %B %Y")

MATH_RULES = (
    r"For any math, physics or chemistry formula, write it in LaTeX. "
    r"Use $...$ for inline formulas, with no spaces just inside the dollar signs. "
    r"Put every display equation in its own $$...$$ block, with the $$ on separate "
    r"lines and a blank line before and after the block. "
    r"Never use \( \) or \[ \] delimiters. "
    r"Never use \begin{aligned}, \begin{align}, \begin{array}, & or \\ line breaks "
    r"inside a formula. Instead, write each step of a calculation as its own "
    r"separate $$...$$ block. "
    r"Never put plain text inside a $$ block, and never put any text right after "
    r"the closing $$ on the same line. "
    r"Never use the dollar sign for money; write Rs or USD instead. "
    r"Write chemical formulas like $\mathrm{H_2SO_4}$ and reactions with "
    r"\rightarrow, and do not use \ce. "
    r"For math, physics and chemistry problems, solve step by step "
    r"and give the final answer clearly. "
)

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
    "By default keep answers short and to the point, about 2 to 5 sentences. "
    "BUT whenever the user asks for details, a detailed or full explanation, an "
    "explanation of a difference or comparison, a summary of a topic, or uses "
    "words like detail, detailed, explain, in depth, تفصیل, تفصیل سے, سمجھاؤ, "
    "وضاحت, فرق, tafseel, tafsil, detail ke sath, तफ़सील, ब्योरा, then write a "
    "thorough answer of about 250 to 500 words, organized with short headings or "
    "bullet points: clear definitions, the key points, examples, and a short "
    "summary. For a difference or comparison, cover each side separately and "
    "then give a comparison list or a markdown table. Never answer such a "
    "request in only one or two sentences. If the user says not to draw a "
    "diagram or picture, answer in text only. "
    "Keep answers simple and polite. "
    "You can also create pictures: when the user asks for an image, the app "
    "generates it for them. Never say that you cannot create images. If the "
    "request for a picture is unclear, ask what they want in it. Drawing "
    "people or faces is allowed, so never say that you cannot draw faces. The "
    "app can also draw labelled science diagrams. "
    + MATH_RULES
)

API_KEY = st.secrets.get("GROQ_API_KEY") or st.secrets.get("GROK_API_KEY")

if not API_KEY:
    st.error("API key نہیں ملی۔ Streamlit secrets میں GROQ_API_KEY شامل کریں۔")
    st.stop()

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

# ---------- Web search (Tavily) ----------
TAVILY_KEY = st.secrets.get("TAVILY_API_KEY")
tavily = TavilyClient(api_key=TAVILY_KEY) if TAVILY_KEY else None


SEARCH_WORDS = [
    "president", "prime minister", "minister", "ceo", "current", "latest",
    "news", "today", "price", "rate", "score", "weather", "who is", "winner",
    "election", "match", "dollar", "gold",
    "صدر", "وزیراعظم", "وزیر اعظم", "وزیر", "آج", "تازہ", "موجودہ", "خبر",
    "قیمت", "ڈالر", "سونا", "میچ", "انتخاب",
    "sadar", "wazir", "aaj", "taza", "maujooda", "khabar", "qeemat",
    "dollar", "sona", "match",
]


def needs_search(text):
    low = (text or "").lower()
    return any(word in low for word in SEARCH_WORDS)


def make_search_query(history):
    """Returns (query, warning). An empty query means: no web search."""
    last = history[-1]["content"] if history else ""
    convo = "\n".join(m["role"] + ": " + m["content"][:300] for m in history[-3:])
    try:
        text = ask_small(
            [
                {
                    "role": "system",
                    "content": (
                        "Today's date is " + today + ". "
                        "Decide whether answering the user's LAST message needs "
                        "up-to-date information from the internet, such as current "
                        "office holders (presidents, prime ministers, CEOs), news, "
                        "prices, sports, weather, or any recent event or fact that "
                        "can change. "
                        "If it is NOT needed (math, science, coding, general "
                        "knowledge, chit-chat), reply with exactly: NO. "
                        "If it is needed, reply with ONLY a short English web search "
                        "query (maximum 10 words) and add the year " + today[-4:]
                        + " when useful. "
                        "Translate Urdu, Roman Urdu or Hindi into English. "
                        "Examples: 'amrika ka sadar kaun hai' -> US president "
                        + today[-4:] + "; 'hello' -> NO; '2+2 kitne hote hain' -> NO; "
                        "'aaj sone ki qeemat' -> gold price today Pakistan. "
                        "Output nothing else."
                    ),
                },
                {"role": "user", "content": convo},
            ],
            max_tokens=300,
        )
    except Exception as error:
        if needs_search(last):
            return last[:200], "⚠️ Search check failed, searched with your text"
        return "", "⚠️ Search check failed: " + str(error)[:80]
    query = (text or "").strip().strip('"').strip()
    said_no = (
        not query
        or query.upper().rstrip(".!") == "NO"
        or re.match(r"(?i)no\s*[.,:;!\-(]", query)
    )
    if said_no:
        if needs_search(last):
            return last[:200], ""
        return "", ""
    return query[:200], ""


def web_context(query):
    if not tavily:
        return "", "TAVILY_API_KEY Secrets میں نہیں ملی"
    try:
        res = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=4,
            include_answer=True,
        )
        parts = []
        if res.get("answer"):
            parts.append("Quick answer: " + res["answer"])
        for r in res.get("results", []):
            parts.append(
                "- " + r.get("title", "") + " (" + r.get("url", "") + "): "
                + r.get("content", "")[:400]
            )
        return "\n".join(parts), ""
    except Exception as error:
        return "", str(error)[:200]


# ---------- YouTube ----------
YT_PATTERN = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:[^\s]*&)?v=|shorts/|embed/|live/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})"
)
DIRECT_LIMIT = 5000
CHUNK_SIZE = 4000
MAX_CHUNKS = 8


def find_youtube_id(text):
    match = YT_PATTERN.search(text or "")
    return match.group(1) if match else ""


def youtube_title(video_id):
    try:
        url = (
            "https://www.youtube.com/oembed?url="
            "https://www.youtube.com/watch?v=" + video_id + "&format=json"
        )
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read().decode("utf-8")).get("title", "")
    except Exception:
        return ""


SUPADATA_KEY = st.secrets.get("SUPADATA_API_KEY")
SUPADATA_URL = "https://api.supadata.ai/v1/transcript"


def library_transcript(video_id):
    """Free method. Often blocked on cloud servers. Returns (text, error)."""
    langs = ["ur", "hi", "en"]
    try:
        api = YouTubeTranscriptApi()
        if hasattr(api, "fetch"):
            try:
                data = api.fetch(video_id, languages=langs)
            except Exception:
                first = next(iter(api.list(video_id)))
                data = first.fetch()
            text = " ".join(s.text for s in data)
        else:
            data = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
            text = " ".join(d["text"] for d in data)
        return text, ""
    except Exception as error:
        return "", str(error).strip()[:80]


def supadata_poll(job_id):
    """Waits for a long (async) Supadata job. Returns (data, error)."""
    headers = {"x-api-key": SUPADATA_KEY}
    deadline = time.time() + 150
    while time.time() < deadline:
        time.sleep(4)
        req = urllib.request.Request(SUPADATA_URL + "/" + job_id, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        status = data.get("status")
        if status == "completed":
            return data, ""
        if status == "failed":
            return None, "Supadata job failed: " + str(data.get("error"))[:100]
    return None, "ویڈیو بہت لمبی ہے، پروسیسنگ وقت پر مکمل نہیں ہوئی"


def supadata_transcript(video_id):
    """Backup method through Supadata. Returns (text, error)."""
    if not SUPADATA_KEY:
        return "", "SUPADATA_API_KEY Secrets میں نہیں ملی"
    mode = "auto" if ai_on else "native"
    try:
        link = "https://www.youtube.com/watch?v=" + video_id
        url = (
            SUPADATA_URL + "?url=" + urllib.parse.quote(link, safe="")
            + "&text=true&mode=" + mode
        )
        req = urllib.request.Request(url, headers={"x-api-key": SUPADATA_KEY})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("jobId") and not data.get("content"):
            data, err = supadata_poll(data["jobId"]) or (None, "poll returned nothing")
            if data is None:
                return "", err
    except urllib.error.HTTPError as error:
        try:
            body = error.read().decode("utf-8")[:150]
        except Exception:
            body = ""
        return "", "HTTP " + str(error.code) + " " + body
    except Exception as error:
        return "", str(error)[:150]
    content = data.get("content") or (data.get("result") or {}).get("content") or ""
    if isinstance(content, list):
        content = " ".join(seg.get("text", "") for seg in content)
    if not content:
        raw = json.dumps(data, ensure_ascii=False)[:150]
        return "", "Supadata نے خالی جواب دیا: " + raw
    return content, ""


def summarize_chunk(chunk, number, total):
    """Detailed notes for one part of a long transcript."""
    for attempt in range(3):
        try:
            return ask_small(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are given part " + str(number) + " of " + str(total)
                            + " of a YouTube video transcript. Write detailed "
                            "bullet-point notes of everything important in this "
                            "part: topics, names, numbers, steps, claims and "
                            "examples. Write in the SAME language and script as the "
                            "transcript (if it is Hindi/Devanagari, use Urdu "
                            "script). Maximum 100 words. Output only the notes."
                        ),
                    },
                    {"role": "user", "content": chunk},
                ]
            ).strip()
        except Exception:
            time.sleep(15)
    return ""


def condense_transcript(text):
    """Short transcripts are used as they are. Long ones become detailed notes."""
    if len(text) <= DIRECT_LIMIT:
        return text
    chunks = [
        text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)
    ][:MAX_CHUNKS]
    notes = []
    for number, chunk in enumerate(chunks, 1):
        note = summarize_chunk(chunk, number, len(chunks))
        if note:
            notes.append("Part " + str(number) + "/" + str(len(chunks)) + ": " + note)
        time.sleep(6)
    if not notes:
        return text[:3500] + " [...video trimmed...] " + text[-1500:]
    result = "\n".join(notes)
    if len(text) > len(chunks) * CHUNK_SIZE:
        result += "\n(Only the first part of this very long video was covered.)"
    return result


def youtube_transcript(video_id):
    """Returns (text, error). Free method first, then Supadata."""
    text, err = library_transcript(video_id) or ("", "library returned nothing")
    if not text:
        text, err2 = supadata_transcript(video_id) or ("", "supadata returned nothing")
        if not text:
            return "", err + " | Supadata: " + err2
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "", "ویڈیو میں کیپشنز نہیں ملے"
    return condense_transcript(text), ""


VIDEO_CTX_CHARS = 5500
HISTORY_CHARS = 6000
HISTORY_CHARS_WITH_VIDEO = 2500


def trim_history(messages, max_chars, per_message=1500):
    """Keeps the newest messages that fit in max_chars. Old long ones are cut."""
    kept = []
    total = 0
    last_index = len(messages) - 1
    for index in range(last_index, -1, -1):
        content = messages[index]["content"]
        if index != last_index and len(content) > per_message:
            content = content[:per_message] + " ..."
        if kept and total + len(content) > max_chars:
            break
        kept.append({"role": messages[index]["role"], "content": content})
        total += len(content)
    return list(reversed(kept))


def video_block(limit):
    """Video transcript text. It is attached to the user's message."""
    text = st.session_state.get("video_text", "")
    if not text:
        return ""
    return (
        "Here is the transcript of the YouTube video the user is talking about "
        "(title: " + st.session_state.get("video_title", "") + "). You DO have "
        "this transcript, so use it.\n\n"
        "=== VIDEO TRANSCRIPT START ===\n" + text[:limit]
        + "\n=== VIDEO TRANSCRIPT END ===\n\n"
        "Rules: Answer from the transcript and give full details: main points "
        "in order, names, numbers, steps and examples. If the user's message "
        "below contains only a YouTube link and no question, write a detailed "
        "summary of the video in Urdu script. If the transcript does not "
        "contain the answer, say so. Do not invent things. For very long "
        "videos the transcript may be condensed notes or only partial. "
        "About names: the transcript was made by automatic speech "
        "recognition, so names of places and people may be misspelled or "
        "misheard. Never replace a name with a different one on your own; keep "
        "names as they appear in the transcript, and if a name looks wrong, say "
        "it may be misheard. If the user corrects a name, use the user's "
        "spelling in this and all later answers."
    )


# ---------- Image generation (Pollinations) ----------
POLLI_KEY = st.secrets.get("POLLINATIONS_API_KEY")

IMAGE_NOUNS = re.compile(
    r"\b(image|images|picture|pictures|photo|photos|pic|pics|logo|painting|"
    r"drawing|sketch|wallpaper|poster|tasveer|tasweer|tasvir|face|faces|chehra|"
    r"diagram|diagrams|flowchart|illustration)\b"
    r"|تصویر|فوٹو|چہرہ|ڈایاگرام|ڈائیگرام|خاکہ|तस्वीर|फोटो|चित्र|चेहरा|आरेख",
    re.I,
)
IMAGE_VERBS = re.compile(
    r"\b(generate|create|make|draw|paint|design|banao|bana|bnao|banado)\b"
    r"|بنا|बना|बनाओ|ڈرا",
    re.I,
)


DRAW_WORDS = re.compile(
    r"\b(draw|paint|sketch|illustrate|portrait|cartoon|render)\b|ڈرا|पेंट|स्केच",
    re.I,
)


NO_DRAW = re.compile(
    r"(?i)\b(don'?t|do not|dont|no|without|never)\s+(?:\w+\s+){0,2}"
    r"(draw|diagram|picture|image|sketch|chart)\b"
    r"|\b(draw|diagram|picture|image|sketch|chart|tasveer)\s+(?:\w+\s+){0,2}"
    r"(mat|na\s+(?:banao|bana))\b"
    r"|(ڈایاگرام|ڈائیگرام|تصویر|ڈرا|خاکہ)\s*(?:\S+\s+){0,2}(مت|نہ)\b"
    r"|\b(مت|نہ)\s*(?:\S+\s+){0,1}(ڈرا|بنانا|بناؤ|ڈایاگرام)"
    r"|(डायग्राम|चित्र|तस्वीर)\s*(?:\S+\s+){0,2}(मत|न)\b"
    r"|मत\s+(बनाओ|बनाना)"
    r"|بغیر\s*(?:\S+\s+){0,1}(ڈایاگرام|ڈائیگرام|تصویر|ڈرا|خاکہ)"
    r"|बिना\s+(?:\S+\s+){0,1}(डायग्राम|चित्र|तस्वीर)"
    r"|\b(bina|bagair|baghair)\s+(?:\w+\s+){0,1}(diagram|tasveer|picture|image)\b"
)


def is_image_request(text):
    """Cheap first check. The small model makes the final decision."""
    text = text or ""
    if len(text) > 400 or NO_DRAW.search(text):
        return False
    return bool(IMAGE_NOUNS.search(text) or DRAW_WORDS.search(text))


REFUSAL_LIKE = re.compile(
    r"(?i)^(i'?m sorry|i am sorry|sorry|i can'?t|i cannot|i am unable|i'?m unable|as an ai)"
)


def last_image_request(history):
    """The description of the most recent picture or diagram made in this chat."""
    for message in reversed(history[:-1]):
        content = message["content"]
        if message["role"] == "assistant" and (
            "[Image generated]" in content or "[Diagram generated]" in content
        ):
            return content.split("]", 1)[1].strip()[:300]
    return ""


def parse_plan(text, last):
    """Returns (kind, text). kind: PICTURE, DIAGRAM, REFUSE or '' (not a request)."""
    text = (text or "").strip().strip('"').strip()
    upper = text.upper()
    if not text or upper.rstrip(".!") == "NO":
        return "", ""
    if upper.startswith("REFUSE"):
        return "REFUSE", ""
    found = re.match(r"(?is)^\s*(PICTURE|DIAGRAM)\s*[:\-]\s*(.+)$", text)
    if found:
        return found.group(1).upper(), found.group(2).strip()[:500]
    if REFUSAL_LIKE.match(text):
        return "PICTURE", last[:300]
    return "PICTURE", text[:400]


def make_image_plan(history):
    """Decides what to make. Returns (kind, text) as in parse_plan."""
    last = history[-1]["content"] if history else ""
    previous = last_image_request(history) if len(last) <= 60 else ""
    content = ""
    if previous:
        content += "Previous image request: " + previous + "\n"
    content += "Last message: " + last[:400]
    try:
        text = ask_small(
            [
                {
                    "role": "system",
                    "content": (
                        "Decide what the user's LAST message wants. Reply in "
                        "exactly one of these forms:\n"
                        "PICTURE: <English prompt for an AI image generator, "
                        "maximum 45 words: subject, style, colors, lighting>\n"
                        "DIAGRAM: <English description of the labelled "
                        "educational diagram to draw: what to show, which labels, "
                        "what to compare>\n"
                        "NO  (the message is not a request to create an image)\n"
                        "REFUSE  (only for sexual content, graphic violence or "
                        "gore, hateful content, or harmful or deceptive images "
                        "of real people)\n"
                        "Rules: Use DIAGRAM for science, maths, geography, "
                        "biology, chemistry or physics concepts, charts, "
                        "flowcharts, structures, comparisons and labelled "
                        "figures. Use PICTURE for artistic or photographic "
                        "images. Drawing people or faces is allowed: never "
                        "refuse just because a person or face is in the image. "
                        "If the user wants a chart or graph of real-world data "
                        "or statistics (prices, populations, results), reply NO, "
                        "because the data would be invented. "
                        "Base your answer on the LAST message only. Use the "
                        "previous image request ONLY if the last message clearly "
                        "refers to it (it, this, same, change, make it...). Never "
                        "bring in unrelated topics. Translate Urdu, Roman Urdu or "
                        "Hindi into English. If the user wants English labels, "
                        "keep the labels in English.\n"
                        "Examples:\n"
                        "'shair ki tasveer banao' -> PICTURE: a majestic lion on "
                        "a rock at golden hour, photorealistic\n"
                        "'ek boorhe aadmi ka chehra banao' -> PICTURE: portrait "
                        "of an elderly man with kind eyes, soft light, detailed\n"
                        "'atom aur ion ka farq tasveer mein samjhao' -> DIAGRAM: "
                        "side by side comparison of a neutral atom and an ion, "
                        "showing nucleus, protons, neutrons and electrons with "
                        "charges labelled\n"
                        "'photo edit kaise karte hain' -> NO"
                    ),
                },
                {"role": "user", "content": content},
            ],
            max_tokens=400,
        )
    except Exception:
        return ("PICTURE", last[:300]) if IMAGE_VERBS.search(last) else ("", "")
    return parse_plan(text, last)


# ---------- Diagrams: the model writes the CONTENT, this code does the drawing ----------
SVG_W = 800
ROW_H = 335
DIAGRAM_KINDS = ("forces", "atom", "flow", "compare")

DIAGRAM_SYSTEM = (
    "You design educational diagrams. You do NOT draw: you only describe the "
    "content as JSON, and the app draws it neatly. Reply with ONE JSON object "
    "and nothing else (no markdown fences). Choose the best 'kind':\n"
    "1) forces: physics situations with forces (Newton's laws, friction, "
    "tension, balanced or unbalanced forces). Fields: kind, title, panels "
    "(1 to 3), each panel: heading, block (name of the object), arrows (1 to 4), "
    "note. Each arrow: side (up, down, left or right; at most ONE arrow per "
    "side), label (max 4 words), length (short, normal or long; equal lengths "
    "mean balanced forces).\n"
    "2) atom: Bohr model of atoms, ions and isotopes. Fields: kind, title, panels "
    "(1 to 3), each panel: heading (for example 'Sodium atom (Na)'), protons, "
    "neutrons, shells (electrons per shell, for example [2,8,1]), note. Do not "
    "write the charge: the app calculates it.\n"
    "3) flow: processes, cycles, sequences and algorithms. Fields: kind, title, "
    "steps (2 to 8), each step: title (max 4 words), detail (max 12 words).\n"
    "4) compare: comparisons and concept summaries. Fields: kind, title, columns "
    "(2 or 3), each column: heading (max 3 words), points (3 to 6 short points, "
    "max 14 words each).\n"
    "Always add 'explanation': 4 to 7 clear sentences explaining the topic, in "
    "the same language and script as the user's original message (Urdu script "
    "for Urdu or Hindi, Roman Urdu for Roman Urdu, English for English), plain "
    "text without LaTeX. All other text (title, headings, labels, notes, "
    "points) must be short English. Be scientifically correct.\n"
    "Example for 'Newton's first law':\n"
    '{"kind":"forces","title":"Newton\'s First Law of Motion","panels":['
    '{"heading":"1. Object at rest","block":"Book on table","arrows":['
    '{"side":"up","label":"Normal force","length":"normal"},'
    '{"side":"down","label":"Weight","length":"normal"}],'
    '"note":"Forces are balanced (net force = 0), so the book stays at rest."},'
    '{"heading":"2. Constant speed","block":"Car on straight road","arrows":['
    '{"side":"right","label":"Driving force","length":"normal"},'
    '{"side":"left","label":"Friction + air drag","length":"normal"},'
    '{"side":"up","label":"Normal force","length":"normal"},'
    '{"side":"down","label":"Weight","length":"normal"}],'
    '"note":"Forces are balanced, so speed and direction do not change."},'
    '{"heading":"3. Unbalanced force","block":"Ball","arrows":['
    '{"side":"right","label":"Push","length":"long"},'
    '{"side":"left","label":"Friction","length":"short"}],'
    '"note":"Net force is not zero, so the ball accelerates."}],'
    '"explanation":"..."}'
)


def wrap_lines(text, width, max_lines=3):
    width = max(8, int(width))
    lines = textwrap.wrap(str(text or "").strip(), width=width) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(1, width - 1)].rstrip(" .,;:") + "…"
    return lines


def svg_text(x, y, text, size=16, anchor="middle", weight="normal",
             fill="#1f2937", style="normal", width=24, max_lines=3):
    """Multi-line text. y is the baseline of the first line."""
    out = ""
    line_h = int(size * 1.3)
    for index, line in enumerate(wrap_lines(text, width, max_lines)):
        out += (
            '<text x="%d" y="%d" font-family="Arial, Helvetica, sans-serif" '
            'font-size="%d" text-anchor="%s" font-weight="%s" font-style="%s" '
            'fill="%s">%s</text>'
            % (x, y + index * line_h, size, anchor, weight, style, fill,
               xml_escape(line))
        )
    return out


def svg_text_v(x, cy, text, size=15, anchor="middle", weight="normal",
               fill="#1f2937", style="normal", width=20, max_lines=2):
    """Like svg_text, but vertically centred around cy."""
    count = len(wrap_lines(text, width, max_lines))
    line_h = int(size * 1.3)
    y = cy - (count - 1) * line_h / 2 + size * 0.35
    return svg_text(x, int(y), text, size, anchor, weight, fill, style, width, max_lines)


def svg_frame(body, height, title):
    head = svg_text(SVG_W // 2, 42, title, 24, "middle", "bold", width=48, max_lines=2)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d">'
        '<defs><marker id="ah" markerUnits="userSpaceOnUse" markerWidth="16" '
        'markerHeight="12" refX="15" refY="6" orient="auto">'
        '<polygon points="0 0, 16 6, 0 12" fill="#1d4ed8"/></marker>'
        '</defs><rect width="%d" height="%d" fill="#ffffff"/>%s%s</svg>'
        % (SVG_W, height, SVG_W, height, head, body)
    )


def render_forces(spec):
    side_len = {"short": 70, "normal": 110, "long": 150}
    vert_len = {"short": 40, "normal": 60, "long": 80}
    body = ""
    panels = spec["panels"]
    for index, panel in enumerate(panels):
        top = 90 + index * ROW_H
        cx, cy = 400, top + 160
        if index:
            body += (
                '<line x1="30" y1="%d" x2="770" y2="%d" stroke="#e5e7eb" '
                'stroke-width="2"/>' % (top - 12, top - 12)
            )
        body += svg_text(30, top + 22, panel["heading"], 18, "start", "bold",
                         width=70, max_lines=1)
        body += (
            '<rect x="%d" y="%d" width="150" height="70" rx="8" fill="#e0e7ff" '
            'stroke="#1f2937" stroke-width="2"/>' % (cx - 75, cy - 35)
        )
        body += svg_text_v(cx, cy, panel["block"], 16, "middle", "bold", width=16,
                           max_lines=2)
        for arrow in panel["arrows"]:
            side, label = arrow["side"], arrow["label"]
            if side in ("up", "down"):
                length = vert_len[arrow["length"]]
                y1 = cy - 35 if side == "up" else cy + 35
                y2 = y1 - length if side == "up" else y1 + length
                body += (
                    '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#1d4ed8" '
                    'stroke-width="4" marker-end="url(#ah)"/>' % (cx, y1, cx, y2)
                )
                body += svg_text_v(cx + 14, (y1 + y2) // 2, label, 15, "start",
                                   width=22, max_lines=2)
            else:
                length = side_len[arrow["length"]]
                x1 = cx + 75 if side == "right" else cx - 75
                x2 = x1 + length if side == "right" else x1 - length
                body += (
                    '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#1d4ed8" '
                    'stroke-width="4" marker-end="url(#ah)"/>' % (x1, cy, x2, cy)
                )
                if side == "right":
                    body += svg_text_v(x2 + 10, cy, label, 15, "start", width=18,
                                       max_lines=3)
                else:
                    body += svg_text_v(x2 - 10, cy, label, 15, "end", width=18,
                                       max_lines=3)
        if panel.get("note"):
            body += svg_text(400, top + 296, panel["note"], 15, "middle",
                             style="italic", fill="#374151", width=88, max_lines=2)
    return svg_frame(body, 90 + len(panels) * ROW_H, spec["title"])


def render_atom(spec):
    panels = spec["panels"]
    count = len(panels)
    panel_w = SVG_W / count
    cy = 330
    scales = []
    for panel in panels:
        r_max = 30 + 26 * len(panel["shells"])
        scales.append(min(1.0, (panel_w - 40) / (2 * r_max)))
    tallest = max((30 + 26 * len(p["shells"])) * s for p, s in zip(panels, scales))
    body = ""
    for index, (panel, scale) in enumerate(zip(panels, scales)):
        cx = int(panel_w * (index + 0.5))
        shells = panel["shells"]
        electrons = sum(shells)
        body += svg_text(cx, 100, panel["heading"], 18, "middle", "bold",
                         width=int(panel_w / 10.5), max_lines=3)
        for k, in_shell in enumerate(shells):
            radius = (30 + 26 * (k + 1)) * scale
            body += (
                '<circle cx="%d" cy="%d" r="%.1f" fill="none" stroke="#9ca3af" '
                'stroke-width="2"/>' % (cx, cy, radius)
            )
            for j in range(in_shell):
                angle = 2 * math.pi * j / in_shell - math.pi / 2 + k * 0.35
                body += (
                    '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#ef4444" '
                    'stroke="#7f1d1d" stroke-width="1"/>'
                    % (cx + radius * math.cos(angle), cy + radius * math.sin(angle),
                       max(4.0, 6 * scale))
                )
        nucleus = max(17.0, 26 * scale)
        body += (
            '<circle cx="%d" cy="%d" r="%.1f" fill="#fbbf24" stroke="#92400e" '
            'stroke-width="2"/>' % (cx, cy, nucleus)
        )
        font = int(max(11, 14 * max(scale, 0.8)))
        body += svg_text(cx, cy - 2, "%dp" % panel["protons"], font, "middle", "bold")
        body += svg_text(cx, cy + font, "%dn" % panel["neutrons"], font, "middle", "bold")
        net = panel["protons"] - electrons
        charge = "0 (neutral)" if net == 0 else ("%+d" % net)
        below = int(cy + tallest + 36)
        body += svg_text(cx, below, "Protons: %d   Electrons: %d" % (panel["protons"], electrons),
                         15, "middle", width=int(panel_w / 8))
        body += svg_text(cx, below + 24, "Net charge: " + charge, 16, "middle", "bold",
                         fill="#b91c1c" if net else "#047857", width=int(panel_w / 8))
        if panel.get("note"):
            body += svg_text(cx, below + 56, panel["note"], 14, "middle", style="italic",
                             fill="#374151", width=int(panel_w / 7.6), max_lines=3)
    return svg_frame(body, int(cy + tallest + 36 + 56 + 70), spec["title"])


def render_flow(spec):
    steps = spec["steps"]
    box_w, box_h, gap, x0 = 620, 84, 44, 90
    y = 90
    body = ""
    for index, step in enumerate(steps):
        body += (
            '<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="#eff6ff" '
            'stroke="#1d4ed8" stroke-width="2"/>' % (x0, y, box_w, box_h)
        )
        body += (
            '<circle cx="%d" cy="%d" r="16" fill="#1d4ed8"/>' % (x0 + 32, y + box_h // 2)
        )
        body += svg_text(x0 + 32, y + box_h // 2 + 6, str(index + 1), 16, "middle",
                         "bold", fill="#ffffff")
        body += svg_text(x0 + 66, y + 30, step["title"], 17, "start", "bold", width=50,
                         max_lines=1)
        if step.get("detail"):
            body += svg_text(x0 + 66, y + 54, step["detail"], 14, "start",
                             fill="#374151", width=64, max_lines=2)
        if index < len(steps) - 1:
            body += (
                '<line x1="400" y1="%d" x2="400" y2="%d" stroke="#1d4ed8" '
                'stroke-width="4" marker-end="url(#ah)"/>'
                % (y + box_h + 2, y + box_h + gap - 3)
            )
        y += box_h + gap
    return svg_frame(body, y - gap + 40, spec["title"])


def render_compare(spec):
    columns = spec["columns"]
    count = len(columns)
    gap = 20
    col_w = (740 - gap * (count - 1)) / count
    chars = max(10, int(col_w / 8.4) - 3)
    wrapped = [[wrap_lines(pt, chars, 5) for pt in col["points"]] for col in columns]
    totals = [sum(len(lines) for lines in col) * 20 + len(col) * 10 for col in wrapped]
    body_h = max(totals) + 24
    colors = ["#dbeafe", "#fce7f3", "#dcfce7"]
    body = ""
    for index, col in enumerate(columns):
        x = int(30 + index * (col_w + gap))
        body += (
            '<rect x="%d" y="90" width="%d" height="44" rx="8" fill="%s" '
            'stroke="#1f2937" stroke-width="2"/>' % (x, col_w, colors[index % 3])
        )
        body += svg_text_v(x + col_w / 2, 112, col["heading"], 18, "middle", "bold",
                           width=int(col_w / 10.5), max_lines=1)
        body += (
            '<rect x="%d" y="134" width="%d" height="%d" rx="8" fill="#ffffff" '
            'stroke="#9ca3af" stroke-width="2"/>' % (x, col_w, body_h)
        )
        y = 162
        for lines in wrapped[index]:
            for n, line in enumerate(lines):
                shown = ("• " + line) if n == 0 else line
                body += svg_text(x + (12 if n == 0 else 23), y, shown, 15, "start",
                                 width=chars + 8, max_lines=1)
                y += 20
            y += 10
    return svg_frame(body, 134 + body_h + 30, spec["title"])


def _text(value, limit=200):
    return str(value or "").strip()[:limit]


def parse_spec(raw):
    """Turns the model's JSON into a safe, complete spec, or None if unusable."""
    found = re.search(r"(?s)\{.*\}", raw or "")
    if not found:
        return None
    try:
        data = json.loads(found.group(0))
        kind = _text(data.get("kind"), 20).lower()
        if kind not in DIAGRAM_KINDS:
            return None
        spec = {
            "kind": kind,
            "title": _text(data.get("title"), 90) or "Diagram",
            "explanation": _text(data.get("explanation"), 2500),
        }
        if kind == "forces":
            panels = []
            for p in data["panels"][:3]:
                used, arrows = set(), []
                for a in p["arrows"]:
                    side = _text(a.get("side"), 10).lower()
                    if side not in ("up", "down", "left", "right") or side in used:
                        continue
                    used.add(side)
                    length = _text(a.get("length"), 10).lower()
                    arrows.append({
                        "side": side,
                        "label": _text(a.get("label"), 60),
                        "length": length if length in ("short", "normal", "long") else "normal",
                    })
                if not arrows:
                    return None
                panels.append({
                    "heading": _text(p.get("heading"), 90),
                    "block": _text(p.get("block"), 40) or "Object",
                    "arrows": arrows,
                    "note": _text(p.get("note"), 180),
                })
            spec["panels"] = panels
        elif kind == "atom":
            panels = []
            for p in data["panels"][:3]:
                shells = [int(n) for n in p["shells"]][:5]
                protons, neutrons = int(p["protons"]), int(p.get("neutrons", 0))
                if not (1 <= protons <= 118 and 0 <= neutrons <= 200):
                    return None
                if not shells or any(n < 0 or n > 32 for n in shells) or sum(shells) > 130:
                    return None
                panels.append({
                    "heading": _text(p.get("heading"), 80),
                    "protons": protons, "neutrons": neutrons, "shells": shells,
                    "note": _text(p.get("note"), 160),
                })
            spec["panels"] = panels
        elif kind == "flow":
            steps = [
                {"title": _text(s.get("title"), 50), "detail": _text(s.get("detail"), 140)}
                for s in data["steps"][:8]
            ]
            if len(steps) < 2:
                return None
            spec["steps"] = steps
        else:
            columns = []
            for c in data["columns"][:3]:
                points = [_text(t, 140) for t in c["points"][:8] if _text(t)]
                if not points:
                    return None
                columns.append({"heading": _text(c.get("heading"), 40), "points": points})
            if len(columns) < 2:
                return None
            spec["columns"] = columns
        if not spec.get("panels") and not spec.get("steps") and not spec.get("columns"):
            return None
        return spec
    except Exception:
        return None


def render_spec(spec):
    kind = spec["kind"]
    if kind == "forces":
        return render_forces(spec)
    if kind == "atom":
        return render_atom(spec)
    if kind == "flow":
        return render_flow(spec)
    return render_compare(spec)


def svg_is_valid(svg):
    try:
        return ET.fromstring(svg).tag.endswith("svg")
    except ET.ParseError:
        return False


def generate_diagram(description, user_text=""):
    """The model writes the content, the app draws it. Returns (svg, explanation, error)."""
    last_error = "ڈایاگرام کا مواد درست فارمیٹ میں نہیں ملا"
    for attempt in range(2):
        try:
            raw = ask_model(
                [
                    {"role": "system", "content": DIAGRAM_SYSTEM},
                    {
                        "role": "user",
                        "content": "Diagram request: " + description
                        + "\nUser's original message (write the explanation in "
                        "its language): " + (user_text or "")[:300],
                    },
                ]
            )
        except Exception as error:
            return None, "", str(error)[:150]
        spec = parse_spec(raw)
        if spec:
            svg = render_spec(spec)
            if svg_is_valid(svg):
                return svg, spec["explanation"], ""
    return None, "", last_error


def show_svg(svg, key):
    """Shows an SVG diagram and its download button."""
    encoded = base64.b64encode(svg.encode("utf-8")).decode()
    st.markdown(
        '<img src="data:image/svg+xml;base64,' + encoded + '" '
        'style="width:100%;background:#fff;border-radius:12px;">',
        unsafe_allow_html=True,
    )
    options = dict(
        label="⬇️ Download diagram (SVG)",
        data=svg,
        file_name="quantum_ai_diagram.svg",
        mime="image/svg+xml",
        key="dl_" + str(key),
    )
    try:
        st.download_button(on_click="ignore", **options)
    except TypeError:
        st.download_button(**options)


def image_download_button(image, key):
    """Shows a download button for generated image bytes."""
    if image[:4] == b"\x89PNG":
        ext, mime = "png", "image/png"
    elif image[8:12] == b"WEBP":
        ext, mime = "webp", "image/webp"
    else:
        ext, mime = "jpg", "image/jpeg"
    options = dict(
        label="⬇️ Download image",
        data=image,
        file_name="quantum_ai_image." + ext,
        mime=mime,
        key="dl_" + str(key),
    )
    try:
        st.download_button(on_click="ignore", **options)
    except TypeError:
        st.download_button(**options)


def generate_image(prompt):
    """Returns (image_bytes, error)."""
    seed = str(random.randint(1, 10**6))
    quoted = urllib.parse.quote(prompt)
    attempts = []
    if POLLI_KEY:
        attempts.append((
            "https://gen.pollinations.ai/image/" + quoted
            + "?model=flux&width=1024&height=1024&seed=" + seed,
            {"Authorization": "Bearer " + POLLI_KEY},
        ))
    attempts.append((
        "https://image.pollinations.ai/prompt/" + quoted
        + "?model=flux&width=1024&height=1024&nologo=true&seed=" + seed,
        {},
    ))
    last_error = "no result"
    for url, extra in attempts:
        for retry in range(2):
            try:
                headers = {"User-Agent": "Mozilla/5.0 (QuantumAI)"}
                headers.update(extra)
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=90) as r:
                    data = r.read()
                    ctype = r.headers.get("Content-Type", "")
                if ctype.startswith("image/") and len(data) > 1000:
                    return data, ""
                last_error = "unexpected response: " + ctype[:40]
                break
            except urllib.error.HTTPError as error:
                last_error = "HTTP " + str(error.code)
                if error.code == 429 and retry == 0:
                    time.sleep(16)
                    continue
                break
            except Exception as error:
                last_error = str(error)[:100]
                break
    return None, last_error


USER_AVATAR = "🧑‍💻"
BOT_AVATAR = LOGO_FILE if has_logo else "🤖"

if "messages" not in st.session_state:
    st.session_state.messages = []

SPEAK_TEMPLATE = r"""
<div style="font-family: sans-serif;">
  <button id="listen" style="background:#6d28d9;color:#fff;border:none;
    border-radius:20px;padding:6px 14px;cursor:pointer;margin-right:6px;">
    🔊 Listen</button>
  <button id="stop" style="background:#3b2a6b;color:#fff;border:none;
    border-radius:20px;padding:6px 14px;cursor:pointer;">
    ⏹ Stop</button>
  <span id="hint" style="color:#cfc2f5;font-size:12px;margin-left:6px;"></span>
</div>
<script>
const text = __TEXT__;
let host = window;
try {
  if (window.parent && window.parent.speechSynthesis) { host = window.parent; }
} catch (e) { host = window; }
const synth = host.speechSynthesis;
const Utter = host.SpeechSynthesisUtterance;
const hint = document.getElementById("hint");
let started = false;

function pickVoice(lang) {
  const voices = synth.getVoices() || [];
  const prefix = lang.slice(0, 2).toLowerCase();
  for (const v of voices) {
    const vl = (v.lang || "").toLowerCase().replace("_", "-");
    if (vl.startsWith(prefix)) { return v; }
  }
  return null;
}

function speakNow() {
  if (!synth || !Utter) { hint.textContent = "Speech not supported"; return; }
  started = false;
  const isUrdu = /[\u0600-\u06FF]/.test(text);
  const lang = isUrdu ? "ur-PK" : "en-US";
  const voice = pickVoice(lang);
  const parts = text.match(/[^.!?\u06D4\u061F\n]+[.!?\u06D4\u061F]*/g) || [text];
  for (const part of parts) {
    const t = part.trim();
    if (!t) { continue; }
    const u = new Utter(t);
    u.lang = lang;
    if (voice) { u.voice = voice; }
    u.rate = 1.1;
    u.onstart = function () { started = true; hint.textContent = ""; };
    synth.speak(u);
  }
  setTimeout(function () {
    if (!started) { hint.textContent = "No sound? Tap Listen."; }
  }, 2500);
}

document.getElementById("listen").onclick = function () {
  if (synth) { synth.cancel(); }
  setTimeout(speakNow, 150);
};
document.getElementById("stop").onclick = function () {
  if (synth) { synth.cancel(); }
};

if (synth && (synth.speaking || synth.pending)) {
  synth.cancel();
  setTimeout(speakNow, 150);
} else {
  setTimeout(speakNow, 250);
}
</script>
"""


def speak_html(text):
    clean = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.S)
    clean = re.sub(r"\$[^$]*\$", " ", clean)
    clean = re.sub(r"[*#`_>~\[\]]", "", clean)
    clean = clean[:2500]
    payload = json.dumps(clean).replace("</", "<\\/")
    return SPEAK_TEMPLATE.replace("__TEXT__", payload)


def clean_display_block(match):
    inner = match.group(1)
    inner = re.sub(r"\\begin\{align\*?\}", r"\\begin{aligned}", inner)
    inner = re.sub(r"\\end\{align\*?\}", r"\\end{aligned}", inner)
    lines = [ln.strip() for ln in inner.split("\n") if ln.strip()]
    return "\n\n$$\n" + "\n".join(lines) + "\n$$\n\n"


def fix_math(text):
    text = re.sub(
        r"\\\[(.+?)\\\]",
        lambda m: "$$" + m.group(1) + "$$",
        text,
        flags=re.S,
    )
    text = re.sub(
        r"\\\((.+?)\\\)",
        lambda m: "$" + m.group(1).strip() + "$",
        text,
        flags=re.S,
    )
    if text.count("$$") % 2 == 1:
        text = text + "\n$$"
    text = re.sub(r"\$\$(.+?)\$\$", clean_display_block, text, flags=re.S)
    text = re.sub(
        r"(?<!\$)\$(?!\$)[ \t]*([^$\n]+?)[ \t]*(?<!\$)\$(?!\$)",
        lambda m: "$" + m.group(1) + "$",
        text,
    )
    return text.strip()


def ask_once(messages, model=None):
    model = model or MODEL_NAME
    try:
        result = client.chat.completions.create(
            model=model,
            messages=messages,
            extra_body={"reasoning_effort": "low"},
        )
    except Exception as error:
        if "reasoning" not in str(error).lower():
            raise
        result = client.chat.completions.create(
            model=model,
            messages=messages,
        )
    return result.choices[0].message.content or ""


def rate_limit_wait(error):
    """Seconds Groq asks us to wait, or None if it is not a rate-limit error."""
    msg = str(error)
    if "429" not in msg:
        return None
    found = re.search(r"try again in (?:(\d+)m)?(\d+(?:\.\d+)?)s", msg)
    if not found:
        return None
    return int(found.group(1) or 0) * 60 + float(found.group(2))


def ask_model(messages):
    """Main model. Short rate limit: wait and retry. Daily limit: backup model."""
    try:
        return ask_once(messages)
    except Exception as error:
        wait = rate_limit_wait(error)
        if wait is None:
            raise
        if wait <= 40:
            time.sleep(wait + 1)
            return ask_once(messages)
        st.session_state.used_backup = True
        return ask_once(messages, SMALL_MODEL)


def ask_small(messages, max_tokens=600):
    """Helper model for small jobs. Its Groq daily limit is separate."""
    try:
        try:
            result = client.chat.completions.create(
                model=SMALL_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                extra_body={"reasoning_effort": "low"},
            )
        except Exception as error:
            if "reasoning" not in str(error).lower():
                raise
            result = client.chat.completions.create(
                model=SMALL_MODEL,
                messages=messages,
                max_tokens=max_tokens,
            )
        return result.choices[0].message.content or ""
    except Exception as error:
        text = str(error).lower()
        if "404" in text or "does not exist" in text or "decommission" in text:
            return ask_once(messages)
        raise


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


def show_message(role, text, image=None, key=0, svg=None, explanation=None):
    avatar = USER_AVATAR if role == "user" else BOT_AVATAR
    with st.chat_message(role, avatar=avatar):
        if role == "user":
            st.markdown('<span class="qa-u"></span>', unsafe_allow_html=True)
            for line in text.split("\n"):
                if line.strip():
                    safe_line = line.replace("]", "\\]")
                    st.markdown(":green[" + safe_line + "]")
        elif svg:
            show_svg(svg, key)
            st.caption(text)
            if explanation:
                st.markdown(explanation)
        elif image:
            st.image(image)
            st.caption(text)
            image_download_button(image, key)
        else:
            st.markdown(text)


if st.session_state.messages:
    if st.button("🗑️ New chat"):
        st.session_state.messages = []
        for key in ("video_id", "video_text", "video_title"):
            st.session_state.pop(key, None)
        st.rerun()
else:
    st.markdown(
        '<div class="qa-welcome">👋 Welcome!<br>'
        "آپ اردو، رومن اردو یا انگریزی میں سوال پوچھ سکتے ہیں۔</div>",
        unsafe_allow_html=True,
    )

for index, message in enumerate(st.session_state.messages):
    show_message(
        message["role"],
        message["content"],
        message.get("image"),
        index,
        message.get("svg"),
        message.get("explanation"),
    )

prompt = st.chat_input("Ask Quantum", accept_audio=True)

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

    if is_image_request(user_text) and not find_youtube_id(user_text):
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            with st.spinner("🎨 تصویر بن رہی ہے..."):
                kind, plan = make_image_plan(st.session_state.messages)
                img, svg, img_err, expl = None, None, "", ""
                if kind == "PICTURE":
                    img, img_err = generate_image(plan)
                elif kind == "DIAGRAM":
                    svg, expl, img_err = generate_diagram(plan, user_text)
                    expl = fix_math(expl) if expl else ""
            slot = len(st.session_state.messages)
            if kind == "REFUSE":
                st.warning("معذرت، اس قسم کی تصویر نہیں بنائی جا سکتی۔")
                st.session_state.messages.pop()
                st.stop()
            elif img:
                st.image(img)
                st.caption("🎨 " + plan)
                image_download_button(img, slot)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": "🎨 [Image generated] " + plan,
                        "image": img,
                    }
                )
                st.stop()
            elif svg:
                show_svg(svg, slot)
                st.caption("📊 " + plan)
                if expl:
                    st.markdown(expl)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": "📊 [Diagram generated] " + plan,
                        "svg": svg,
                        "explanation": expl,
                    }
                )
                st.stop()
            elif kind:
                st.error("⚠️ تصویر نہیں بن سکی: " + img_err)
                st.session_state.messages.pop()
                st.stop()
            # kind == "": not an image request after all, continue normally

    recent = st.session_state.messages[-MAX_HISTORY:]

    with st.chat_message("assistant", avatar=BOT_AVATAR):
        text_box = st.container()
        speak_box = st.container()
        answer = None
        search_note = ""
        video_note = ""

        with text_box:
            with st.spinner("Thinking..."):
                try:
                    extra = ""
                    video_note = ""
                    vid = find_youtube_id(user_text)
                    if vid and vid != st.session_state.get("video_id"):
                        for key in ("video_id", "video_text", "video_title"):
                            st.session_state.pop(key, None)
                        transcript, yt_err = youtube_transcript(vid) or ("", "no result returned")
                        if transcript:
                            st.session_state.video_id = vid
                            st.session_state.video_text = transcript
                            st.session_state.video_title = youtube_title(vid)
                            video_note = "🎬 YouTube transcript loaded"
                        else:
                            video_note = "⚠️ YouTube transcript failed: " + yt_err
                    if vid:
                        query, qwarn = "", ""
                    else:
                        query, qwarn = make_search_query(st.session_state.messages) or (
                            "", "⚠️ search check returned nothing"
                        )
                    if query:
                        info, err = web_context(query) or ("", "no result returned")
                        if info:
                            search_note = "🔎 Web search: " + query
                            extra = (
                                "\n\nFRESH WEB SEARCH RESULTS (searched today, "
                                + today + ", for: " + query + "):\n" + info
                                + "\n\nFor current facts, answer ONLY from these "
                                "results. Ignore your own memory and ignore any "
                                "earlier answers in this chat that disagree with "
                                "them. If the results do not clearly contain the "
                                "answer, say you could not confirm it."
                            )
                        else:
                            search_note = "⚠️ Search failed: " + (err or "no results")
                    if vid and not st.session_state.get("video_text"):
                        extra += (
                            "\n\nThe user shared a YouTube link but its transcript "
                            "could not be read. Do NOT guess what the video "
                            "contains. Tell the user honestly that you could not "
                            "read this video."
                        )
                    if not query and not qwarn and not vid:
                        search_note = "ℹ️ No web search for this question"
                    search_note = (
                        video_note + "  " + qwarn + "  " + search_note
                    ).strip()
                    has_video = bool(st.session_state.get("video_text"))
                    history_chars = (
                        HISTORY_CHARS_WITH_VIDEO if has_video else HISTORY_CHARS
                    )

                    def attempt(video_limit, hist_chars):
                        history = trim_history(
                            st.session_state.messages[-MAX_HISTORY:], hist_chars
                        )
                        video_text = video_block(video_limit)
                        if video_text and history:
                            last = history[-1]
                            history[-1] = {
                                "role": last["role"],
                                "content": (
                                    video_text + "\n\nUSER MESSAGE:\n"
                                    + last["content"]
                                ),
                            }
                        system = system_text + extra
                        return fix_math(
                            ask_model([{"role": "system", "content": system}] + history)
                        )

                    try:
                        answer = attempt(VIDEO_CTX_CHARS, history_chars)
                    except Exception as first_error:
                        too_big = (
                            "413" in str(first_error)
                            or "too large" in str(first_error).lower()
                        )
                        if not too_big:
                            raise
                        answer = attempt(2500, 1200)
                        search_note = (search_note + "  ✂️ Context shortened").strip()
                    if st.session_state.pop("used_backup", False):
                        search_note = (
                            search_note + "  ↪️ Backup model (main daily limit reached)"
                        ).strip()
                except Exception as error:
                    st.session_state.messages.pop()
                    msg = str(error)
                    if "429" in msg or "rate limit" in msg.lower():
                        if "(TPD)" in msg:
                            kind = "روزانہ"
                        elif "(TPM)" in msg:
                            kind = "فی منٹ"
                        else:
                            kind = "روزانہ یا فی منٹ"
                        wait = rate_limit_wait(error)
                        if wait is None:
                            when = "کچھ دیر"
                        elif wait >= 60:
                            when = "تقریباً " + str(int(wait // 60) + 1) + " منٹ"
                        else:
                            when = "تقریباً " + str(int(wait) + 1) + " سیکنڈ"
                        st.error(
                            "⏳ Groq کی " + kind + " مفت حد پوری ہو گئی ہے۔ "
                            + when + " بعد دوبارہ کوشش کریں۔"
                        )
                    else:
                        st.error("Error: " + msg)
                        st.code(traceback.format_exc()[-700:])

        if answer is not None:
            if speak_on and answer.strip():
                with speak_box:
                    components.html(speak_html(answer), height=48)
            with text_box:
                st.markdown(answer)
                if search_note:
                    st.caption(search_note)
                if video_note.startswith("🎬") and st.session_state.get("video_text"):
                    with st.expander("📄 Video transcript (check names here)"):
                        st.write(st.session_state.video_text)
            st.session_state.messages.append(
                {"role": "assistant", "content": answer}
            )
