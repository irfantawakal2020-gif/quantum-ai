import base64
from datetime import date
import io
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
import tempfile
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

def square_logo():
    """Crops a wide or tall logo to a square around the emblem. Returns a file path."""
    try:
        from PIL import Image, ImageChops

        out = os.path.join(tempfile.gettempdir(), "quantum_ai_logo_square.png")
        if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(LOGO_FILE):
            return out
        im = Image.open(LOGO_FILE).convert("RGB")
        w, h = im.size
        corners = [im.getpixel(p) for p in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3))]
        background = tuple(sum(c[i] for c in corners) // 4 for i in range(3))
        diff = ImageChops.difference(im, Image.new("RGB", im.size, background))
        box = diff.convert("L").point(lambda p: 255 if p > 45 else 0).getbbox()
        if not box:
            box = (0, 0, w, h)
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        side = max(box[2] - box[0], box[3] - box[1]) * 1.3
        side = min(max(side, 64), min(w, h))
        left = min(max(cx - side / 2, 0), w - side)
        top = min(max(cy - side / 2, 0), h - side)
        square = im.crop((int(left), int(top), int(left + side), int(top + side)))
        square.resize((512, 512), Image.LANCZOS).save(out, "PNG")
        return out
    except Exception:
        return LOGO_FILE


has_logo = os.path.exists(LOGO_FILE)
logo_path = square_logo() if has_logo else None

st.set_page_config(
    page_title="Quantum AI",
    page_icon=logo_path or "🤖",
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
    object-fit: cover;
    object-position: center;
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
    with open(logo_path, "rb") as f:
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
camera_on = st.toggle("📷 Camera: take a photo and ask about it", value=False)
cam, cam_text, send_cam = None, "", False
if camera_on:
    cam_n = st.session_state.get("cam_n", 0)
    cam = st.camera_input("Take a photo", key="cam_%d" % cam_n)
    cam_text = st.text_input(
        "Question about the photo (optional)", key="camq_%d" % cam_n
    )
    send_cam = st.button(
        "📤 Send photo", key="camsend_%d" % cam_n, disabled=cam is None
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
    "SPELLING: write every word with correct, standard spelling. In Urdu script "
    "use standard Pakistani Urdu spelling, as in Urdu newspapers and Urdu "
    "dictionaries, never Hindi or Arabic spellings, and never drop, add or swap "
    "letters. Write names of people and places with care; if you are not sure "
    "how a name is spelled in Urdu, write it in English letters instead of "
    "guessing. In Roman Urdu use the common simple spellings consistently, for "
    "example: hai, nahi, kyun, kaise, aap, tafseel. Reread your answer once "
    "before sending it and fix any spelling mistake. "
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
    "dollar", "sona", "match", "steam", "discount", "sale", "keemat", "kimat",
    "release", "stock",
]


def needs_search(text):
    low = (text or "").lower()
    return any(word in low for word in SEARCH_WORDS)


def parse_search_plan(text, last):
    """Returns {"queries": [...], "steam": "..."} or None when no search is needed."""
    text = (text or "").strip()
    found = re.search(r"(?s)\{.*\}", text)
    if found:
        try:
            data = json.loads(found.group(0))
            queries = [
                str(q).strip()[:150] for q in (data.get("queries") or []) if str(q).strip()
            ][:3]
            steam = str(data.get("steam") or "").strip()[:80]
            if queries or steam:
                return {"queries": queries or [last[:150]], "steam": steam}
            return None
        except Exception:
            pass
    plain = text.strip('"').strip()
    if (
        not plain
        or plain.upper().rstrip(".!") == "NO"
        or re.match(r"(?i)no\s*[.,:;!\-(]", plain)
        or re.search(r"[{}\[\]@#<>|]", plain)
        or len(plain) > 200
    ):
        return None
    return {"queries": [plain[:150]], "steam": ""}


def make_search_plan(history):
    """Returns (plan, warning). plan is None when no web search is needed."""
    last = history[-1]["content"] if history else ""
    convo = "\n".join(m["role"] + ": " + m["content"][:300] for m in history[-3:])
    fallback = {"queries": [last[:150]], "steam": ""}
    year = today[-4:]
    try:
        text = ask_small(
            [
                {
                    "role": "system",
                    "content": (
                        "Today's date is " + today + ". "
                        "Decide whether answering the user's LAST message needs "
                        "up-to-date information from the internet: current office "
                        "holders, news, prices, sales and discounts, sports, "
                        "weather, releases, or any fact that can change. "
                        "Reply with ONLY one JSON object: "
                        '{"search": true or false, "queries": [...], "steam": "..."}. '
                        "If search is true, give 2 or 3 short English web search "
                        "queries (maximum 10 words each) that look at the question "
                        "from different angles; include the year " + year + " when "
                        "useful and the exact product or edition names. Translate "
                        "Urdu, Roman Urdu or Hindi into English. Set steam to the "
                        "official Steam store game title ONLY when the user asks "
                        "about a game's price, discount or details on Steam (for "
                        "example GTA 5 -> Grand Theft Auto V); otherwise use an "
                        "empty string. If no internet is needed (maths, science, "
                        "coding, general knowledge, chit-chat) reply "
                        '{"search": false, "queries": [], "steam": ""}.\n'
                        "Examples:\n"
                        "'amrika ka sadar kaun hai' -> "
                        '{"search": true, "queries": ["US president ' + year + '", '
                        '"who is the current president of the United States"], '
                        '"steam": ""}\n'
                        "'GTA 5 ki Steam par keemat kya hai' -> "
                        '{"search": true, "queries": ["GTA 5 Steam price ' + year + '", '
                        '"GTA V Enhanced Steam current price discount"], '
                        '"steam": "Grand Theft Auto V"}\n'
                        "'hello' -> "
                        '{"search": false, "queries": [], "steam": ""}'
                    ),
                },
                {"role": "user", "content": convo},
            ],
            max_tokens=400,
        )
    except Exception as error:
        if needs_search(last):
            return fallback, "⚠️ Search check failed, searched with your text"
        return None, "⚠️ Search check failed: " + str(error)[:80]
    plan = parse_search_plan(text, last)
    if plan is None and needs_search(last):
        plan = fallback
    return plan, ""


def steam_price(title):
    """Live prices from the public Steam store search. Returns text, or '' if none."""
    lines = []
    for region in ("pk", "us"):
        url = (
            "https://store.steampowered.com/api/storesearch/?term="
            + urllib.parse.quote(title) + "&l=english&cc=" + region
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (QuantumAI)"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception:
            continue
        for item in (data.get("items") or [])[:5]:
            name = item.get("name", "?")
            price = item.get("price")
            if isinstance(price, dict) and price.get("final") is not None:
                final = price["final"] / 100.0
                initial = (price.get("initial") or price["final"]) / 100.0
                text = "%s %.2f" % (price.get("currency", ""), final)
                if initial > final:
                    text += " (normal price %.2f, %d%% off)" % (
                        initial, round((1 - final / initial) * 100)
                    )
                lines.append("- [%s store] %s: %s" % (region.upper(), name, text))
            else:
                lines.append(
                    "- [%s store] %s: no price listed (free, unreleased or not sold here)"
                    % (region.upper(), name)
                )
    if not lines:
        return ""
    return (
        "STEAM STORE LIVE DATA (official Steam store search, prices as listed today):\n"
        + "\n".join(lines)
    )


def web_context(queries, steam_title=""):
    """Runs the searches. Returns (text, error, sources)."""
    parts, sources, seen, errors = [], [], set(), []
    steam = steam_price(steam_title) if steam_title else ""
    if steam:
        parts.append(steam)
    if not tavily:
        if parts:
            return "\n".join(parts), "", sources
        return "", "TAVILY_API_KEY Secrets میں نہیں ملی", []
    for index, query in enumerate(queries[:3]):
        try:
            res = tavily.search(
                query=query,
                search_depth="advanced" if index == 0 else "basic",
                max_results=5,
                include_answer=(index == 0),
            )
        except Exception as error:
            errors.append(str(error)[:100])
            continue
        if index == 0 and res.get("answer"):
            parts.append("Quick answer (may be incomplete): " + res["answer"])
        for r in res.get("results", []):
            url = r.get("url", "")
            if not url or url in seen or len(sources) >= 8:
                continue
            seen.add(url)
            title = r.get("title") or url
            parts.append("- " + title + " (" + url + "): " + (r.get("content") or "")[:550])
            sources.append({"title": title[:90], "url": url})
    if not sources and not steam:
        return "", "; ".join(errors) or "no results", []
    return "\n".join(parts), "", sources


def find_photos(query):
    """Real photos from the web (through Tavily). Returns (urls, sources, error)."""
    if not tavily:
        return [], [], "TAVILY_API_KEY Secrets میں نہیں ملی"
    try:
        res = tavily.search(query=query, search_depth="basic", max_results=4,
                            include_images=True)
    except Exception as error:
        return [], [], str(error)[:150]
    urls = []
    for item in res.get("images") or []:
        link = item.get("url") if isinstance(item, dict) else item
        if isinstance(link, str) and link.startswith("http") and link not in urls:
            urls.append(link)
    sources = [
        {"title": (r.get("title") or r.get("url", ""))[:90], "url": r.get("url", "")}
        for r in res.get("results", [])[:4] if r.get("url")
    ]
    return urls[:4], sources, ("" if urls else "کوئی تصویر نہیں ملی")


def show_sources(sources, label="🔎 Sources"):
    """A folded list of the pages an answer is based on."""
    if not sources:
        return
    with st.expander(label):
        for item in sources[:10]:
            title = (item.get("title") or item["url"]).replace("[", "(").replace("]", ")")
            st.markdown("- [" + title + "](" + item["url"].replace(")", "%29") + ")")


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


TEACH_WORDS = re.compile(
    r"(?i)\b(explain|explanation|understand|teach|law|laws|theory|concept|principle|"
    r"formula|process|cycle|structure|working|how does|how do|difference|differences|"
    r"compare|comparison|versus|vs|samjh\w*|samajh\w*|qanoon|farq|nizam)\b"
    r"|سمجھ|وضاحت|قانون|فرق|اصول|نظریہ|समझ|नियम|फर्क|अंतर|सिद्धांत"
)
ART_WORDS = re.compile(
    r"(?i)\b(cartoon|anime|portrait|logo|poster|wallpaper|landscape|painting|"
    r"realistic|photorealistic|face|faces|chehra|funny|cute|fantasy|sunset)\b"
    r"|چہرہ|कार्टून|चेहरा"
)


def route_override(kind, plan, last):
    """Pictures cannot write correct text, so teaching requests become diagrams."""
    if kind == "PICTURE" and TEACH_WORDS.search(last) and not ART_WORDS.search(last):
        return "DIAGRAM", last[:300]
    return kind, plan


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
    found = re.match(r"(?is)^\s*(PICTURE|DIAGRAM|PHOTO)\s*[:\-]\s*(.+)$", text)
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
                        "PHOTO: <English web search query for REAL existing "
                        "photographs>\n"
                        "NO  (the message is not a request to create an image)\n"
                        "REFUSE  (only for sexual content, graphic violence or "
                        "gore, hateful content, or harmful or deceptive images "
                        "of real people)\n"
                        "Rules: Use DIAGRAM for science, maths, geography, "
                        "biology, chemistry or physics concepts, charts, "
                        "flowcharts, structures, comparisons and labelled "
                        "figures. If the image is meant to EXPLAIN or TEACH "
                        "anything (a law, concept, process, how something "
                        "works, any school subject), use DIAGRAM even if the "
                        "user says 'picture' or 'tasveer', because picture "
                        "generators cannot write correct text. Use PICTURE only "
                        "for artistic, imaginary or photographic images: animals, "
                        "people, faces, scenes, logos, cartoons, posters. Use "
                        "PICTURE for artistic or photographic "
                        "images. Use PHOTO (not PICTURE) when the user wants to SEE or "
                        "FIND real existing photographs of a place, landmark, "
                        "animal, object, product, event or famous public figure "
                        "(dikhao, show me, photos of); use PICTURE when the user "
                        "wants an image CREATED (banao, draw, generate). Never "
                        "use PHOTO for private individuals: reply REFUSE. "
                        "Drawing people or faces is allowed: never "
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
                        "'newton ka pehla qanoon tasveer se samjhao' -> DIAGRAM: "
                        "Newton's first law with balanced and unbalanced forces\n"
                        "'badshahi mosque ki photo dikhao' -> PHOTO: Badshahi Mosque "
                        "Lahore photos\n"
                        "'photo edit kaise karte hain' -> NO"
                    ),
                },
                {"role": "user", "content": content},
            ],
            max_tokens=400,
        )
    except Exception:
        if IMAGE_VERBS.search(last):
            return route_override("PICTURE", last[:300], last)
        return "", ""
    kind, plan = parse_plan(text, last)
    return route_override(kind, plan, last)


# ---------- Diagrams: the model writes the CONTENT, this code does the drawing ----------
SVG_W = 800
ROW_H = 335
DIAGRAM_KINDS = ("forces", "atom", "flow", "compare", "illustrated")

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
    "5) illustrated: a real-world setup, apparatus, organ, plant, machine or "
    "place whose parts must be shown and explained (for example a chemistry "
    "lab setup, a human heart, a microscope). Fields: kind, title, scene (an "
    "English prompt for an AI picture generator that describes ONLY what to "
    "see: objects, layout, style; NO text, labels or letters), items (3 to 8), "
    "each item: name (max 4 words), detail (max 14 words).\n"
    "Always add 'explanation': a clear explanatory paragraph in ENGLISH, 7 to "
    "10 sentences (about 110 to 170 words), with the key ideas, causes and a "
    "real-world example. It is written INSIDE the picture. Plain text, no "
    "LaTeX, no bullet points. All other text (title, headings, labels, notes, "
    "points) must also be short English. Be scientifically correct.\n"
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


def svg_frame(body, height, title, explanation=""):
    head = svg_text(SVG_W // 2, 42, title, 24, "middle", "bold", width=48, max_lines=2)
    extra = ""
    total = height
    if explanation:
        lines = wrap_lines(explanation, 94, 22)
        box_h = 62 + len(lines) * 19 + 14
        top = height + 6
        extra = (
            '<rect x="30" y="%d" width="740" height="%d" rx="10" fill="#f8fafc" '
            'stroke="#cbd5e1" stroke-width="2"/>' % (top, box_h)
        )
        extra += svg_text(46, top + 32, "Explanation", 17, "start", "bold")
        extra += svg_text(46, top + 60, explanation, 15, "start", width=94, max_lines=22)
        total = top + box_h + 24
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d">'
        '<defs><marker id="ah" markerUnits="userSpaceOnUse" markerWidth="16" '
        'markerHeight="12" refX="15" refY="6" orient="auto">'
        '<polygon points="0 0, 16 6, 0 12" fill="#1d4ed8"/></marker>'
        '</defs><rect width="%d" height="%d" fill="#ffffff"/>%s%s%s</svg>'
        % (SVG_W, total, SVG_W, total, head, body, extra)
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
    return svg_frame(body, 90 + len(panels) * ROW_H, spec["title"], spec.get("explanation", ""))


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
    return svg_frame(body, int(cy + tallest + 36 + 56 + 70), spec["title"], spec.get("explanation", ""))


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
    return svg_frame(body, y - gap + 40, spec["title"], spec.get("explanation", ""))


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
    return svg_frame(body, 134 + body_h + 30, spec["title"], spec.get("explanation", ""))


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
        elif kind == "illustrated":
            items = [
                {"name": _text(i.get("name"), 50), "detail": _text(i.get("detail"), 140)}
                for i in data["items"][:8] if _text(i.get("name"))
            ]
            scene = _text(data.get("scene"), 500)
            if len(items) < 2 or not scene:
                return None
            spec["scene"], spec["items"] = scene, items
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
        if not any(spec.get(k) for k in ("panels", "steps", "columns", "items")):
            return None
        return spec
    except Exception:
        return None


def image_mime(data):
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def render_illustrated(spec, image):
    """A generated picture, then the list of parts, then the explanation."""
    pic = 520
    x0 = (SVG_W - pic) // 2
    top = 90
    encoded = base64.b64encode(image).decode()
    body = (
        '<rect x="%d" y="%d" width="%d" height="%d" rx="6" fill="#f3f4f6" '
        'stroke="#1f2937" stroke-width="2"/>' % (x0 - 4, top - 4, pic + 8, pic + 8)
    )
    body += (
        '<image x="%d" y="%d" width="%d" height="%d" '
        'preserveAspectRatio="xMidYMid slice" href="data:%s;base64,%s"/>'
        % (x0, top, pic, pic, image_mime(image), encoded)
    )
    y = top + pic + 46
    body += svg_text(30, y, "Parts and their roles", 17, "start", "bold")
    y += 16
    for index, item in enumerate(spec["items"]):
        name_lines = wrap_lines(item["name"], 22, 2)
        detail_lines = wrap_lines(item["detail"], 62, 3)
        row_h = max(len(name_lines), len(detail_lines)) * 19 + 12
        body += (
            '<rect x="30" y="%d" width="740" height="%d" fill="%s"/>'
            % (y, row_h, "#eff6ff" if index % 2 == 0 else "#ffffff")
        )
        body += svg_text(44, y + 20, item["name"], 15, "start", "bold", width=22, max_lines=2)
        body += svg_text(260, y + 20, item["detail"], 15, "start", width=62, max_lines=3)
        y += row_h
    return svg_frame(body, y + 24, spec["title"], spec.get("explanation", ""))


def illustrated_as_table(spec):
    """If the picture cannot be made, show the parts as a table instead."""
    return {
        "kind": "compare",
        "title": spec["title"],
        "explanation": spec.get("explanation", ""),
        "columns": [
            {"heading": "Part", "points": [i["name"] for i in spec["items"]]},
            {"heading": "Role", "points": [i["detail"] or "-" for i in spec["items"]]},
        ],
    }


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
                        + "\nUser's original message: " + (user_text or "")[:300],
                    },
                ]
            )
        except Exception as error:
            return None, "", str(error)[:150]
        spec = parse_spec(raw)
        if spec:
            if spec["kind"] == "illustrated":
                image, _ = generate_image(
                    spec["scene"] + ", clean educational illustration, white background"
                )
                svg = (
                    render_illustrated(spec, image)
                    if image
                    else render_spec(illustrated_as_table(spec))
                )
            else:
                svg = render_spec(spec)
            if svg_is_valid(svg):
                return svg, "", ""
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
    quoted = urllib.parse.quote(
        prompt[:380] + ", no text, no letters, no words, no captions"
    )
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


# ---------- Photos: the user sends a picture, a vision model reads it ----------
MAX_IMAGES = 3
MAX_SIDE = 1280
DEFAULT_IMAGE_QUESTION = (
    "اس تصویر کا تفصیل سے تجزیہ کرو اور بتاؤ اس میں کیا ہے۔ اگر اس میں کوئی "
    "سوال یا مسئلہ ہو تو اسے قدم بہ قدم حل کرو۔"
)
VISION_MODELS = [
    m for m in (
        st.secrets.get("VISION_MODEL"),
        "qwen/qwen3.8-27b",
        "meta-llama/llama-4-scout-17b-16e-instruct",
    ) if m
]


def prepare_image(data):
    """Straightens (phone rotation), shrinks and re-encodes a photo as JPEG bytes."""
    try:
        from PIL import Image, ImageOps

        photo = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        photo.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        photo.save(out, "JPEG", quality=85)
        return out.getvalue()
    except Exception:
        return None


def describe_images(images, question):
    """Asks a vision model to read the photos. Returns (description, error)."""
    content = [{
        "type": "text",
        "text": (
            "User's question or request: " + (question or "")[:500] + "\n\n"
            "Describe everything visible in detail. Transcribe ALL text exactly as "
            "written (in any language), including equations, numbers, tables and "
            "labels. Describe charts, diagrams, objects, colors and layout. If the "
            "image contains a question or a problem, copy it completely and "
            "accurately. Say what is unclear. Do not identify real people from "
            "their faces."
        ),
    }]
    for data in images[:MAX_IMAGES]:
        content.append({
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(data).decode()},
        })
    messages = [{"role": "user", "content": content}]
    last_error = "no vision model available"
    for model in VISION_MODELS:
        for attempt in range(2):
            try:
                try:
                    result = client.chat.completions.create(
                        model=model, messages=messages, max_tokens=1800,
                        temperature=0.2, extra_body={"reasoning_format": "hidden"},
                    )
                except Exception as error:
                    if "reasoning" not in str(error).lower():
                        raise
                    result = client.chat.completions.create(
                        model=model, messages=messages, max_tokens=1800, temperature=0.2,
                    )
                text = re.sub(
                    r"(?s)<think>.*?</think>", "", result.choices[0].message.content or ""
                ).strip()
                if text:
                    return text, ""
                last_error = "empty answer from " + model
                break
            except Exception as error:
                message = str(error)
                last_error = message[:150]
                wait = rate_limit_wait(error)
                if wait is not None and wait <= 40 and attempt == 0:
                    time.sleep(wait + 1)
                    continue
                break
    return "", last_error


def image_block(limit=3500):
    """The analysis of the user's latest photo, attached to the user's message."""
    info = st.session_state.get("image_info", "")
    if not info:
        return ""
    return (
        "The user shared a photo. A vision model analyzed it and its analysis is "
        "below. You CAN use it. Answer from it; if the question needs a detail "
        "that is not in the analysis, say so instead of guessing. If the photo "
        "contains a question or problem, solve it step by step following your "
        "usual rules. Never identify real people from their faces.\n\n"
        "=== IMAGE ANALYSIS START ===\n" + info[:limit] + "\n=== IMAGE ANALYSIS END ==="
    )


USER_AVATAR = "🧑‍💻"
BOT_AVATAR = logo_path or "🤖"

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
            temperature=0.4,
            extra_body={"reasoning_effort": "low"},
        )
    except Exception as error:
        if "reasoning" not in str(error).lower():
            raise
        result = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.4,
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
                temperature=0.2,
                extra_body={"reasoning_effort": "low"},
            )
        except Exception as error:
            if "reasoning" not in str(error).lower():
                raise
            result = client.chat.completions.create(
                model=SMALL_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2,
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
            temperature=0.2,
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


def show_message(role, text, image=None, key=0, svg=None, explanation=None,
                 photos=None, sources=None, user_images=None):
    avatar = USER_AVATAR if role == "user" else BOT_AVATAR
    with st.chat_message(role, avatar=avatar):
        if role == "user":
            st.markdown('<span class="qa-u"></span>', unsafe_allow_html=True)
            for line in text.split("\n"):
                if line.strip():
                    safe_line = line.replace("]", "\\]")
                    st.markdown(":green[" + safe_line + "]")
            if user_images:
                st.image(user_images, width=180)
        elif svg:
            show_svg(svg, key)
            if explanation:
                st.markdown(explanation)
        elif photos:
            st.image(photos, width=240)
            st.caption(text)
            show_sources(sources, "📎 Sources")
        elif image:
            st.image(image)
            st.caption(text)
            image_download_button(image, key)
        else:
            st.markdown(text)
            show_sources(sources)


if st.session_state.messages:
    if st.button("🗑️ New chat"):
        st.session_state.messages = []
        for key in ("video_id", "video_text", "video_title", "image_info"):
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
        message.get("photos"),
        message.get("sources"),
        message.get("images"),
    )

try:
    prompt = st.chat_input(
        "Ask Quantum",
        accept_audio=True,
        accept_file="multiple",
        file_type=["png", "jpg", "jpeg", "webp"],
    )
except TypeError:
    prompt = st.chat_input("Ask Quantum", accept_audio=True)

camera_send = bool(send_cam and cam is not None)

if prompt or camera_send:
    user_text = (prompt.text if prompt else "") or ""
    files = list(getattr(prompt, "files", None) or []) if prompt else []
    images = []

    if camera_send:
        files = [cam]
        user_text = (cam_text or "").strip()
        st.session_state.cam_n = st.session_state.get("cam_n", 0) + 1

    audio = getattr(prompt, "audio", None) if prompt else None
    if audio:
        try:
            spoken = transcribe(audio.getvalue())
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

    for file in files[:MAX_IMAGES]:
        prepared = prepare_image(file.getvalue())
        if prepared:
            images.append(prepared)
    if files and not images:
        st.warning("تصویر پڑھی نہیں جا سکی۔ jpg، png یا webp تصویر بھیجیں۔")
        st.stop()
    if images and not user_text.strip():
        user_text = DEFAULT_IMAGE_QUESTION

    if not user_text.strip():
        st.stop()

    new_message = {"role": "user", "content": user_text}
    if images:
        new_message["images"] = images
    st.session_state.messages.append(new_message)
    show_message("user", user_text, user_images=images)

    if is_image_request(user_text) and not find_youtube_id(user_text) and not images:
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            with st.spinner("🎨 تصویر بن رہی ہے..."):
                kind, plan = make_image_plan(st.session_state.messages)
                img, svg, img_err, expl = None, None, "", ""
                photos, photo_sources = [], []
                if kind == "PICTURE":
                    img, img_err = generate_image(plan)
                elif kind == "PHOTO":
                    photos, photo_sources, img_err = find_photos(plan)
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
            elif photos:
                st.image(photos, width=240)
                st.caption("📷 " + plan)
                show_sources(photo_sources, "📎 Sources")
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": "📷 [Photos] " + plan,
                        "photos": photos,
                        "sources": photo_sources,
                    }
                )
                st.stop()
            elif kind:
                st.error(
                    ("⚠️ تصاویر نہیں مل سکیں: " if kind == "PHOTO"
                     else "⚠️ تصویر نہیں بن سکی: ") + img_err
                )
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
        sources = []

        with text_box:
            with st.spinner("Thinking..."):
                try:
                    extra = ""
                    video_note = ""
                    image_note = ""
                    if images:
                        description, vision_error = describe_images(
                            images, user_text
                        ) or ("", "no result")
                        if description:
                            st.session_state.image_info = description
                            image_note = "🖼️ Image analyzed"
                        else:
                            st.session_state.pop("image_info", None)
                            image_note = "⚠️ Image analysis failed: " + vision_error
                            extra += (
                                "\n\nThe user sent a photo but it could not be "
                                "analyzed. Do NOT guess what it shows; tell the "
                                "user honestly that the photo could not be read."
                            )
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
                    if vid or images:
                        plan, qwarn = None, ""
                    else:
                        plan, qwarn = make_search_plan(st.session_state.messages) or (
                            None, "⚠️ search check returned nothing"
                        )
                    query = plan["queries"][0] if plan else ""
                    if plan:
                        info, err, found_sources = web_context(
                            plan["queries"], plan["steam"]
                        ) or ("", "no result returned", [])
                        if info:
                            sources = found_sources
                            search_note = "🔎 Web search: " + " | ".join(plan["queries"])
                            if plan["steam"]:
                                search_note += " | Steam store: " + plan["steam"]
                            extra = (
                                "\n\nFRESH WEB SEARCH RESULTS (searched today, "
                                + today + ", for: " + "; ".join(plan["queries"])
                                + "):\n" + info
                                + "\n\nHow to use these results: rely on them, not "
                                "on your memory, and ignore earlier answers in this "
                                "chat that disagree. Give the concrete facts you "
                                "find (exact prices with currency, dates, names, "
                                "editions) and say where they come from. Prices and "
                                "offers change and differ by region, so say 'as "
                                "listed' and name the region when known. If the "
                                "results are incomplete or conflict, still share the "
                                "best information you have and say clearly what is "
                                "uncertain; never answer only 'I cannot find it'. "
                                "Lines marked STEAM STORE LIVE DATA are the most "
                                "reliable source for Steam prices."
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
                    if not query and not qwarn and not vid and not images:
                        search_note = "ℹ️ No web search for this question"
                    search_note = (
                        video_note + "  " + image_note + "  " + qwarn + "  " + search_note
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
                        image_text = image_block(
                            3500 if video_limit >= VIDEO_CTX_CHARS else 1500
                        )
                        prefix = "\n\n".join(t for t in (video_text, image_text) if t)
                        if prefix and history:
                            last = history[-1]
                            history[-1] = {
                                "role": last["role"],
                                "content": (
                                    prefix + "\n\nUSER MESSAGE:\n" + last["content"]
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
                show_sources(sources)
                if video_note.startswith("🎬") and st.session_state.get("video_text"):
                    with st.expander("📄 Video transcript (check names here)"):
                        st.write(st.session_state.video_text)
            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "sources": sources}
            )
