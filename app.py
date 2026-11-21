import base64
from datetime import date
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

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
[data-testid="stChatInput"] button {
    border-radius: 50% !important;
    width: 38px !important;
    height: 38px !important;
    min-width: 38px !important;
    padding: 0 !important;
    display: flex;
    align-items: center;
    justify-content: center;
}
[data-testid="stChatInputSubmitButton"] {
    background: linear-gradient(135deg, #8b5cf6, #5b21b6) !important;
    color: #fff !important;
    box-shadow: 0 0 12px rgba(139, 92, 246, 0.6);
}
[data-testid="stChatInputSubmitButton"]:disabled {
    background: rgba(255, 255, 255, 0.12) !important;
    box-shadow: none;
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
    "Keep normal answers short and to the point, about 2 to 5 sentences, "
    "unless the user asks for details. "
    "Keep answers simple and polite. "
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
    for word in SEARCH_WORDS:
        pattern = r"(?<![a-z])" + re.escape(word) + r"s?(?![a-z])"
        if re.search(pattern, low):
            return True
    return False


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
            data, err = supadata_poll(data["jobId"])
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
    text, err = library_transcript(video_id)
    if not text:
        text, err2 = supadata_transcript(video_id)
        if not text:
            return "", err + " | Supadata: " + err2
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "", "ویڈیو میں کیپشنز نہیں ملے"
        return condense_transcript(text), ""
    
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


def ask_once(messages):
    try:
        result = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            extra_body={"reasoning_effort": "low"},
        )
    except Exception as error:
        if "reasoning" not in str(error).lower():
            raise
        result = client.chat.completions.create(
            model=MODEL_NAME,
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
    """Like ask_once, but waits and retries once on a short rate limit."""
    try:
        return ask_once(messages)
    except Exception as error:
        wait = rate_limit_wait(error)
        if wait is None or wait > 40:
            raise
        time.sleep(wait + 1)
        return ask_once(messages)


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


def show_message(role, text):
    avatar = USER_AVATAR if role == "user" else BOT_AVATAR
    with st.chat_message(role, avatar=avatar):
        if role == "user":
            st.markdown('<span class="qa-u"></span>', unsafe_allow_html=True)
            for line in text.split("\n"):
                if line.strip():
                    safe_line = line.replace("]", "\\]")
                    st.markdown(":green[" + safe_line + "]")
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

for message in st.session_state.messages:
    show_message(message["role"], message["content"])

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

    recent = st.session_state.messages[-MAX_HISTORY:]

    with st.chat_message("assistant", avatar=BOT_AVATAR):
        text_box = st.container()
        speak_box = st.container()
        answer = None
        search_note = ""

        with text_box:
            with st.spinner("Thinking..."):
                try:
                    extra = ""
                    video_note = ""
                    vid = find_youtube_id(user_text)
                    if vid and vid != st.session_state.get("video_id"):
                        for key in ("video_id", "video_text", "video_title"):
                            st.session_state.pop(key, None)
                        transcript, yt_err = youtube_transcript(vid)
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
                        query, qwarn = make_search_query(st.session_state.messages)
                    if query:
                        info, err = web_context(query)
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
                    if st.session_state.get("video_text"):
                        extra += (
                            "\n\nYOUTUBE VIDEO TRANSCRIPT (title: "
                            + st.session_state.get("video_title", "")
                            + "):\n" + st.session_state.video_text
                            + "\n\nThe user is asking about this video. Answer "
                            "from the transcript and give full details: main "
                            "points in order, names, numbers, steps and examples. "
                            "If the user shared only the link without a question, "
                            "give a detailed summary. If the transcript does not "
                            "contain the answer, say so. Do not invent things. "
                            "For very long videos the transcript may be condensed "
                            "notes or only partial."
                        )
                    elif vid:
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
                    answer = fix_math(
                        ask_model(
                            [{"role": "system", "content": system_text + extra}]
                            + recent
                        )
                    )
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

        if answer is not None:
            if speak_on and answer.strip():
                with speak_box:
                    components.html(speak_html(answer), height=48)
            with text_box:
                st.markdown(answer)
                if search_note:
                    st.caption(search_note)
            st.session_state.messages.append(
                {"role": "assistant", "content": answer}
            )
