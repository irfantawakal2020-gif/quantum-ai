import base64
from datetime import date
import difflib
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

# Your own Ollama server (set these three in Streamlit Secrets, never in the code)
CUSTOM_URL = str(st.secrets.get("CUSTOM_API_URL") or "").strip()
CUSTOM_KEY = str(st.secrets.get("CUSTOM_API_KEY") or "").strip()
CUSTOM_MODEL = str(st.secrets.get("CUSTOM_MODEL") or "").strip()

mic_choice = st.radio(
    "🎤 Mic language",
    ["Auto", "English", "اردو"],
    horizontal=True,
)
speak_on = st.toggle("🔊 Read answers aloud", value=False)
fix_on = st.toggle(
    "✍️ اردو املا کی جانچ (ہر اردو جواب پر ایک اضافی درخواست لگتی ہے)",
    value=True,
)
use_custom = st.toggle(
    "🏠 جوابات کے لیے اپنا Ollama سرور استعمال کریں",
    value=bool(CUSTOM_URL),
    disabled=not CUSTOM_URL,
    help="پہلے Secrets میں CUSTOM_API_URL اور CUSTOM_API_KEY لکھیں",
)
ai_on = st.toggle(
    "🎙 AI transcript for videos without captions (uses Supadata credits)",
    value=True,
)
camera_on = st.toggle(
    "📷 Quick camera (low quality). For sharp photos use the + button, then Camera",
    value=False,
)
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

# A second way to attach photos and files, in case the + button of the chat box fails
up_n = st.session_state.get("up_n", 0)
with st.expander("📎 تصویر یا فائل اپلوڈ کریں (اگر نیچے + کام نہ کرے)"):
    up_files = st.file_uploader(
        "تصاویر، PDF یا ٹیکسٹ فائلیں چنیں",
        accept_multiple_files=True,
        key="up_%d" % up_n,
    )
    up_text = st.text_input(
        "سوال (اختیاری). خالی چھوڑیں تو ایپ خود تجزیہ کرے گی",
        key="upq_%d" % up_n,
    )
    send_up = st.button(
        "📤 بھیجیں", key="upsend_%d" % up_n, disabled=not up_files
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
    "URDU WRITING QUALITY: in Urdu script prefer short, simple sentences and "
    "common everyday words. If you are not sure of a rare or literary word, use "
    "a simpler word you are sure about. Never invent words and never glue two "
    "words together. Always use the Urdu letters ی ک ہ (never the Arabic letters "
    "ي ك ه). Write these correctly and separately: کے لیے, اس کی, اس کے, ان کا, "
    "ان کی, جس کا, کیونکہ, نہیں, میں, ہیں, چاہیے, کیا, گیا, لیکن, بھی, اگر, "
    "تو, پھر, جبکہ, یعنی. Do not put any Chinese, Russian, Thai or Devanagari "
    "characters inside an Urdu answer. "
    "UNDERSTANDING: first work out what the user's LAST message is really about. "
    "A video, photo or document shared earlier is only background: use it "
    "only when the question is about it. If the user says the question has "
    "nothing to do with it, believe them, drop it and answer the question "
    "itself. Never reply that something is not mentioned in the video, photo "
    "or document when the question is about something else. "
    "CONVERSATION: pay attention to the whole conversation and to what the user "
    "really means, not only to the last message. Never repeat an earlier answer "
    "word for word. If the user says they did not understand, asks the same "
    "thing again, or corrects you, explain it differently (simpler words, a new "
    "example, another angle) or ask ONE short question about what exactly is "
    "unclear. If a request is ambiguous, ask a short clarifying question "
    "instead of guessing. "
    "By default keep answers short and to the point, about 2 to 5 sentences. "
    "BUT whenever the user asks for details, a detailed or full explanation, an "
    "explanation of a difference or comparison, a summary of a topic, or uses "
    "words like detail, detailed, explain, in depth, تفصیل, تفصیل سے, سمجھاؤ, "
    "فرق, وضاحت, tafseel, tafsil, detail ke sath, तफ़सील, ब्योरा, then write a "
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
if not API_KEY and not CUSTOM_URL:
    st.error(
        "کوئی انجن نہیں ملا۔ Streamlit secrets میں CUSTOM_API_URL (اپنا سرور) "
        "یا GROQ_API_KEY میں سے کم از کم ایک شامل کریں۔"
    )
    st.stop()

# client is None when there is no Groq key: then everything goes to your own server
client = (
    OpenAI(api_key=API_KEY, base_url="https://api.groq.com/openai/v1")
    if API_KEY
    else None
)
NO_GROQ_NOTE = "یہ کام Groq key کے بغیر نہیں ہو سکتا (GROQ_API_KEY شامل کریں)"

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


def photo_links(photos):
    """Open/save links for photos found on the web (they are not files we hold)."""
    if not photos:
        return
    links = " ".join(
        "[⬇️ تصویر %d](%s)" % (n, url.replace(")", "%29"))
        for n, url in enumerate(photos, 1)
    )
    st.markdown(links)
    st.caption("لنک دبا کر تصویر کھولیں، پھر اسے دیر تک دبا کر محفوظ کریں۔")


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
HISTORY_CHARS = 8000
HISTORY_CHARS_WITH_VIDEO = 3500


def trim_history(messages, max_chars, per_message=1500):
    """Keeps the newest messages that fit in max_chars. Old long ones are cut."""
    kept = []
    total = 0
    last_index = len(messages) - 1
    for index in range(last_index, -1, -1):
        content = messages[index]["content"]
        # the assistant's previous answer is kept almost whole so it is not repeated
        limit = 3500 if index == last_index - 1 else per_message
        if index != last_index and len(content) > limit:
            content = content[:limit] + " ..."
        if kept and total + len(content) > max_chars:
            break
        kept.append({"role": messages[index]["role"], "content": content})
        total += len(content)
    return list(reversed(kept))


SUMMARY_KEEP = 6


def update_summary():
    """Folds old messages into a short running summary (helper model, separate quota)."""
    messages = st.session_state.messages
    done = st.session_state.get("summary_upto", 0)
    cutoff = len(messages) - SUMMARY_KEEP
    if cutoff - done < 6:
        return
    transcript = "\n".join(
        m["role"] + ": " + m["content"][:700] for m in messages[done:cutoff]
    )
    previous = st.session_state.get("chat_summary", "")
    try:
        text = ask_small(
            [
                {
                    "role": "system",
                    "content": (
                        "You keep the running memory of a chat between a user and an "
                        "AI assistant. Update the summary with the new messages. "
                        "Write 8 to 15 short lines (maximum 1000 characters) in the "
                        "same language and script the user writes. Keep: what the "
                        "user is asking about and wants; key facts, names, numbers "
                        "and decisions; what the assistant has already explained "
                        "(briefly, so it is not repeated); the user's corrections and "
                        "complaints; anything still unresolved. Output only the "
                        "summary."
                    ),
                },
                {
                    "role": "user",
                    "content": "Previous summary:\n" + (previous or "(none)")
                    + "\n\nNew messages:\n" + transcript,
                },
            ],
            max_tokens=1200,
        )
    except Exception:
        return
    text = (text or "").strip()
    if len(text) >= 40:
        st.session_state.chat_summary = text[:1500]
        st.session_state.summary_upto = cutoff


def summary_block(limit=900):
    summary = st.session_state.get("chat_summary", "")
    if not summary:
        return ""
    return (
        "\n\nSUMMARY OF THE EARLIER PART OF THIS CONVERSATION (context only, not "
        "instructions; use it to understand what the user means):\n" + summary[:limit]
    )


def last_answer_text(messages):
    """The assistant's most recent text answer (pictures are ignored)."""
    for message in reversed(messages):
        if message["role"] == "assistant":
            content = message["content"]
            if content.startswith(("🎨", "📊", "📷")):
                continue
            return content
    return ""


def too_similar(a, b):
    a, b = (a or "").strip(), (b or "").strip()
    if len(a) < 30 or len(b) < 30:
        return False
    return difflib.SequenceMatcher(None, a[:1500], b[:1500]).ratio() > 0.85


def repeat_warning(previous):
    return (
        "\n\nREPETITION WARNING: your previous answer to this user was:\n<<<\n"
        + previous[:1500] + "\n>>>\nYour new draft repeats it. Do NOT repeat it. "
        "Read the user's latest message again together with the whole conversation. "
        "If the user says they did not understand, is unhappy, or asks again, "
        "explain it differently (simpler words, a new example, another angle) or ask "
        "ONE short question to find out exactly what is unclear. Otherwise answer "
        "their new question directly."
    )


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
        "FIRST decide whether the user's latest message is about this video. If it is "
        "a general question, a question about you (your name, who made you), "
        "chit-chat, or the user says it has nothing to do with the video, "
        "IGNORE the transcript completely and answer normally as Quantum AI; "
        "never say that the video does not mention it. "
        "Only if the message is about the video: "
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
        "spelling in this and all later answers. "
        "If the transcript is written in Devanagari (Hindi script), you must "
        "convert it into Urdu script letter by letter, and be most careful with "
        "names of people, places and organisations. Letter map: च=چ, छ=چھ, "
        "ज=ج, झ=جھ, श=ش, ष=ش, स=س, ख=خ, ग=گ, घ=گھ, क=ک, फ=ف, ड=ڈ, ट=ٹ, "
        "त=ت, थ=تھ, द=د, ध=دھ, ब=ب, भ=بھ, प=پ, म=م, न=ن, र=ر, ल=ل, व=و, "
        "ह=ہ. For example बलोच is بلوچ (never بلوش) and श is never used for च. "
        "Do not change a name into a different one."
    )


# ---------- Image generation (Pollinations) ----------
POLLI_KEY = st.secrets.get("POLLINATIONS_API_KEY")

IMAGE_NOUNS = re.compile(
    r"\b(image|images|picture|pictures|photo|photos|pic|pics|logo|painting|"
    r"drawing|sketch|wallpaper|poster|tasveer|tasweer|tasvir|face|faces|chehra|"
    r"diagram|diagrams|flowchart|illustration)\b"
    r"|خاکہ|ڈائیگرام|ڈایاگرام|چہرہ|فوٹو|تصویر|तस्वीर|फोटो|चित्र|चेहरा|आरेख",
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
    r"|(ڈرا|بنانا|بناؤ|ڈایاگرام|ڈائیگرام|تصویر|خاکہ)\s+(?:\S+\s+){0,2}(مت|نہ)"
    r"|(مت|نہ)\s+(?:\S+\s+){0,2}(ڈایاگرام|ڈائیگرام|تصویر|ڈرا|خاکہ)"
    r"|(डायग्राम|चित्र|तस्वीर)\s*(?:\S+\s+){0,2}(मत|न)\b"
    r"|मत\s+(बनाओ|बनाना)"
    r"|بغیر\s+(?:\S+\s+){0,1}(ڈایاگرام|ڈائیگرام|تصویر|ڈرا|خاکہ)"
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
    r"|نظریہ|اصول|فرق|قانون|وضاحت|سمجھ|समझ|नियम|फर्क|अंतर|सिद्धांत"
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
    """Returns (kind, text). kind: PICTURE, DIAGRAM, PHOTO, REFUSE or '' (not a request)."""
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
                        "NO (the message is not a request to create an image)\n"
                        "REFUSE (only for sexual content, graphic violence or "
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
    if kind == "PHOTO" and IMAGE_VERBS.search(last):
        kind = "PICTURE"
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
        body += svg_text(cx, below, "Protons: %d Electrons: %d" % (panel["protons"], electrons),
                         15, "middle", width=int(panel_w / 8))
        body += svg_text(cx, below + 24, "Net charge: " + charge, 16, "middle", "bold",
                         fill="#b91c1c" if net else "#047857", width=int(panel_w / 8))
        if panel.get("note"):
            body += svg_text(cx, below + 56, panel["note"], 14, "middle", style="italic",
                             fill="#374151", width=int(panel_w / 7.6), max_lines=3)
    return svg_frame(body, int(cy + tallest + 36 + 56 + 70), spec["title"],
                     spec.get("explanation", ""))


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
MAX_SIDE = 2000
DEFAULT_IMAGE_QUESTION = (
    "اس تصویر کا تفصیل سے تجزیہ کرو اور بتاؤ اس میں کیا ہے۔ اگر اس میں کوئی "
    "سوال یا مسئلہ ہو تو اسے قدم بہ قدم حل کرو۔"
)
DEFAULT_DOC_QUESTION = "اس فائل کا خلاصہ اور اہم نکات بتاؤ۔"
VISION_MODELS = [
    m for m in (
        st.secrets.get("VISION_MODEL"),
        "qwen/qwen3.8-27b",
        "meta-llama/llama-4-scout-17b-16e-instruct",
    ) if m
]

try:  # iPhone HEIC photos, if the optional package is installed
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:
    pass

PATTERN_WORDS = re.compile(
    r"(?i)\b(pattern|example|method|approach|template|same way|same style|same format|"
    r"like this|learn|follow|tarika|tareeqa|tariqa|isi tarah|isi tarhan|misal|seekh|"
    r"dekh\s*lo|dekho)\b"
    r"|तरीका|नमूना|پیٹرن|طریقہ|طریقے|اسی طرح|اسی انداز|مثال|سیکھ|دیکھ لو|انداز|"
    r"पैटर्न|इसी तरह|उदाहरण"
)
UNCLEAR_WORDS = re.compile(
    r"(?i)\[unclear\]|unreadable|illegible|not legible|cannot read|can't read|"
    r"too blurry|can't make out|cannot make out|hard to read"
)


def prepare_image(data):
    """Straightens (phone rotation), shrinks and re-encodes a photo as JPEG bytes."""
    try:
        from PIL import Image, ImageFile, ImageFilter, ImageOps

        ImageFile.LOAD_TRUNCATED_IMAGES = True  # half-saved gallery or camera files
        Image.MAX_IMAGE_PIXELS = 300_000_000
        photo = Image.open(io.BytesIO(data))
        try:
            photo.draft("RGB", (MAX_SIDE * 2, MAX_SIDE * 2))  # fast decode of huge JPEGs
        except Exception:
            pass
        photo = ImageOps.exif_transpose(photo)
        if photo.mode in ("RGBA", "LA", "P"):
            photo = photo.convert("RGBA")
            page = Image.new("RGBA", photo.size, (255, 255, 255, 255))
            page.alpha_composite(photo)
            photo = page
        photo = photo.convert("RGB")
        width, height = photo.size
        if max(width, height) < 1400:  # small camera photo: enlarge so text is easier to read
            scale = 1400.0 / max(width, height)
            photo = photo.resize((int(width * scale), int(height * scale)), Image.LANCZOS)
        photo.thumbnail((MAX_SIDE, MAX_SIDE))
        photo = ImageOps.autocontrast(photo, cutoff=1)
        photo = photo.filter(ImageFilter.UnsharpMask(radius=1.6, percent=110, threshold=3))
        out = io.BytesIO()
        photo.save(out, "JPEG", quality=90)
        return out.getvalue()
    except Exception:
        return None


def rotate_jpeg(data, angle):
    try:
        from PIL import Image

        photo = Image.open(io.BytesIO(data)).rotate(
            angle, expand=True, fillcolor=(255, 255, 255)
        )
        out = io.BytesIO()
        photo.save(out, "JPEG", quality=90)
        return out.getvalue()
    except Exception:
        return None


def unclear_score(text):
    return len(UNCLEAR_WORDS.findall(text or ""))


def vision_call(image, question):
    """One request with one photo. Returns (text, error)."""
    if client is None:
        return "", "تصویر پڑھنے کے لیے Groq key درکار ہے (GROQ_API_KEY شامل کریں)"
    content = [
        {
            "type": "text",
            "text": (
                "Context from the user (for focus only, do not answer it): "
                + (question or "")[:400] + "\n\n"
                "Your job is to READ this photo as accurately as possible. The photo "
                "may be tilted, rotated, upside down, mirrored, blurry or shadowed: "
                "read it anyway, mentally correcting the angle. 1) Transcribe ALL "
                "text exactly as written, in any language, line by line: questions, "
                "given data, numbers, units, equations, table cells, labels. 2) If it "
                "shows a SOLVED example, transcribe EVERY step in order: each "
                "formula, substitution, calculation, unit, the final answer, and the "
                "layout (headings, numbering, how steps are arranged). 3) Describe "
                "diagrams, circuits, graphs and figures precisely (shapes, labels, "
                "values, arrows, directions). 4) Describe other objects, colors and "
                "layout briefly. Write [unclear] for any part you cannot read; never "
                "guess numbers and never refuse because of the angle or quality. Do "
                "not identify real people from their faces."
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image).decode()},
        },
    ]
    messages = [{"role": "user", "content": content}]
    last_error = "no vision model available"
    for model in VISION_MODELS:
        for attempt in range(2):
            try:
                try:
                    result = client.chat.completions.create(
                        model=model, messages=messages, max_tokens=2200,
                        temperature=0.1, extra_body={"reasoning_format": "hidden"},
                    )
                except Exception as error:
                    if "reasoning" not in str(error).lower():
                        raise
                    result = client.chat.completions.create(
                        model=model, messages=messages, max_tokens=2200, temperature=0.1,
                    )
                text = re.sub(
                    r"(?s)<think>.*?</think>", "", result.choices[0].message.content or ""
                ).strip()
                if text:
                    return text, ""
                last_error = "empty answer from " + model
                break
            except Exception as error:
                last_error = str(error)[:150]
                wait = rate_limit_wait(error)
                if wait is not None and wait <= 40 and attempt == 0:
                    time.sleep(wait + 1)
                    continue
                break
    return "", last_error


def read_photo(data, question):
    """Reads one photo. If it comes back unclear, retries rotated by 90 and 270 degrees."""
    text, error = vision_call(data, question)
    if text and unclear_score(text) < 3:
        return text, ""
    best = text
    for angle in (90, 270, 10, -10):
        rotated = rotate_jpeg(data, angle)
        if not rotated:
            continue
        again, _ = vision_call(rotated, question)
        if again and (not best or unclear_score(again) < unclear_score(best)):
            best = again
        if again and unclear_score(again) < 3:
            break
    return (best, "") if best else ("", error)


def describe_images(images, question):
    """Reads each photo separately (keeps every request under the token limit)."""
    parts, errors = [], []
    for number, data in enumerate(images[:MAX_IMAGES], 1):
        text, error = read_photo(data, question)
        if text:
            parts.append(("PHOTO %d:\n" % number if len(images) > 1 else "") + text)
        else:
            errors.append(error)
    if parts:
        return "\n\n".join(parts), ""
    return "", "; ".join(errors)[:200]


def image_block(limit=3500, fresh_reference=False):
    """Photo transcriptions (and a saved reference example) for the user's message."""
    reference = st.session_state.get("reference_info", "")
    info = st.session_state.get("image_info", "")
    if not reference and not info:
        return ""
    text = (
        "The user shared photo(s). A vision model read them and its transcription "
        "is below. You CAN use it, but only when the user's message is about the "
        "photo; for a general question or a question about you, ignore it and "
        "answer normally. Answer from it; if something is marked [unclear] "
        "or missing, say so instead of guessing. If a photo contains a question or "
        "problem, solve it step by step following your usual rules. Never identify "
        "real people from their faces."
    )
    if reference:
        text += (
            "\n\n=== REFERENCE EXAMPLE (the user showed it earlier; their instruction "
            "was: " + st.session_state.get("reference_task", "")[:300] + ") ===\n"
            + reference[:limit] + "\n=== END REFERENCE EXAMPLE ===\n"
            "For every new question the user gives (typed or as a photo), solve it "
            "step by step following EXACTLY the same pattern as this reference "
            "example: same order of steps, same formulas and style, same layout, "
            "until the user says otherwise."
        )
        if fresh_reference:
            text += (
                " In THIS reply do not solve anything yet: first list in 3 to 6 short "
                "points the pattern you noticed (steps, formulas, layout), say you "
                "will use it, and ask for the next question."
            )
    if info:
        text += (
            "\n\n=== LATEST PHOTO TRANSCRIPTION ===\n" + info[:limit]
            + "\n=== END LATEST PHOTO ==="
        )
    return text


# ---------- Documents: PDF, TXT, CSV ... ----------
DOC_TYPES = ("pdf", "txt", "csv", "md", "json")


def read_document(data, ext):
    """Returns the text of a PDF or text file, or '' if it could not be read."""
    try:
        if ext == "pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((p.extract_text() or "") for p in reader.pages[:30])
        else:
            text = data.decode("utf-8", errors="ignore")
        return re.sub(r"\n{3,}", "\n\n", text).strip()
    except Exception:
        return ""


def doc_block(limit=9000):
    text = st.session_state.get("doc_text", "")
    if not text:
        return ""
    return (
        "The user uploaded document(s). Their text is below. You CAN use it. "
        "Use it only when the user's message is about the document; for a general "
        "question or a question about you, ignore it and answer normally. "
        "If the message is about the document but the text does not contain the answer, say so. "
        "Do not invent things.\n"
        "=== DOCUMENT START ===\n" + text[:limit] + "\n=== DOCUMENT END ==="
    )


USER_AVATAR = "🧑"
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


# ---------- Model calls ----------
def ask_once(messages, model=None, temperature=0.4):
    model = model or MODEL_NAME
    try:
        result = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            extra_body={"reasoning_effort": "low"},
        )
    except Exception as error:
        if "reasoning" not in str(error).lower():
            raise
        result = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
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


def flatten_messages(messages):
    """Turns the chat list into one plain prompt for a simple /generate endpoint."""
    names = {"system": "System", "user": "User", "assistant": "Assistant"}
    parts = [names.get(m["role"], m["role"]) + ": " + m["content"] for m in messages]
    return "\n\n".join(parts) + "\n\nAssistant:"


def custom_call(messages, temperature=0.4):
    """Sends the chat to your own server. Returns (raw_text, error)."""
    if not CUSTOM_URL:
        return "", "CUSTOM_API_URL Secrets میں نہیں ملی"
    body = {
        "prompt": flatten_messages(messages),
        "messages": messages,
        "stream": False,
        "temperature": temperature,
    }
    if CUSTOM_MODEL:
        body["model"] = CUSTOM_MODEL
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (QuantumAI)",
    }
    if CUSTOM_KEY:
        headers["Authorization"] = "Bearer " + CUSTOM_KEY
        headers["X-API-Key"] = CUSTOM_KEY
    request = urllib.request.Request(
        CUSTOM_URL, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=95) as r:
            return r.read().decode("utf-8", errors="replace"), ""
    except urllib.error.HTTPError as error:
        try:
            detail = error.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            detail = ""
        return "", "HTTP " + str(error.code) + " " + detail
    except Exception as error:
        return "", str(error)[:200]


def parse_custom_reply(raw):
    """Finds the answer text in the reply of a simple or OpenAI-style server."""
    raw = (raw or "").strip()
    try:
        data = json.loads(raw)
    except Exception:
        return raw
    text = ""
    if isinstance(data, str):
        text = data
    elif isinstance(data, dict):
        for key in ("response", "text", "output", "answer", "reply", "content",
                    "result", "generated_text"):
            if isinstance(data.get(key), str) and data[key].strip():
                text = data[key]
                break
        if not text and isinstance(data.get("message"), dict):
            text = str(data["message"].get("content") or "")
        if not text and isinstance(data.get("choices"), list) and data["choices"]:
            first = data["choices"][0] or {}
            text = str((first.get("message") or {}).get("content") or first.get("text") or "")
    return re.sub(r"(?s)<think>.*?</think>", "", text).strip()


def prefer_custom():
    """True when requests should go to your own server first."""
    if not CUSTOM_URL:
        return False
    if client is None:
        return True
    if not use_custom:
        return False
    # after a failure, use Groq for a minute instead of waiting again
    return time.time() - st.session_state.get("custom_down", 0) > 60


def custom_chat(messages, temperature=0.4):
    """Returns (answer, error) from your own server."""
    raw, error = custom_call(messages, temperature)
    if error:
        st.session_state.custom_down = time.time()
        return "", error
    text = parse_custom_reply(raw)
    if not text:
        st.session_state.custom_down = time.time()
        return "", "سرور کا جواب سمجھ نہیں آیا: " + raw[:150]
    st.session_state.pop("custom_down", None)
    return text, ""


def ask_model(messages, temperature=0.4, custom=False):
    """Main model. Short rate limit: wait and retry. Daily limit: backup model."""
    if prefer_custom() or (custom and CUSTOM_URL and client is not None):
        text, error = custom_chat(messages, temperature)
        if text:
            st.session_state.custom_used = True
            return text
        st.session_state.custom_error = error
        if client is None:
            raise RuntimeError("آپ کے اپنے سرور سے جواب نہیں ملا: " + error)
    try:
        return ask_once(messages, None, temperature)
    except Exception as error:
        wait = rate_limit_wait(error)
        if wait is None:
            raise
        if wait <= 40:
            time.sleep(wait + 1)
            return ask_once(messages, None, temperature)
        st.session_state.used_backup = True
        return ask_once(messages, SMALL_MODEL, temperature)


def ask_small(messages, max_tokens=600):
    """Helper model for small jobs. Its Groq daily limit is separate."""
    if prefer_custom():
        text, error = custom_chat(messages, 0.2)
        if text:
            return text
        if client is None:
            raise RuntimeError("آپ کے اپنے سرور سے جواب نہیں ملا: " + error)
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


if CUSTOM_URL:
    with st.expander("🧪 اپنے سرور کا ٹیسٹ"):
        if st.button("ٹیسٹ کریں", key="custom_test"):
            with st.spinner("سرور سے رابطہ ہو رہا ہے..."):
                raw_reply, test_error = custom_call(
                    [{"role": "user", "content": "Say hello in one short sentence."}], 0.2
                )
            if test_error:
                st.error("رابطہ نہیں ہوا: " + test_error)
            else:
                st.success("رابطہ ہو گیا۔ سرور کا اصل جواب نیچے ہے:")
                st.code(raw_reply[:600])
                st.write("ایپ کو جو متن سمجھ آیا:", parse_custom_reply(raw_reply) or "(کچھ نہیں)")


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


# ---------- Urdu spelling: cleaning and proofreading of the answer ----------
ARABIC_FIXES = {"ي": "ی", "ى": "ی", "ك": "ک", "ه": "ہ", "ة": "ہ"}
STRAY_SCRIPTS = re.compile(
    r"[\u0400-\u04FF\u0E00-\u0E7F\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF]"
)
PROTECT = re.compile(
    r"```.*?```|\$\$.*?\$\$|\$[^$\n]+?\$|https?://\S+|`[^`\n]+`", re.S
)
PROOF_SYSTEM = (
    "You are a professional Urdu proofreader, like a copy editor at a Pakistani "
    "newspaper. The user gives you a text written by an AI. Fix ONLY spelling "
    "and writing mistakes: wrong, missing, extra or swapped letters; words "
    "wrongly joined or wrongly split; Hindi or Arabic spellings used instead of "
    "standard Pakistani Urdu spelling; wrong letters such as ي ك ه instead of "
    "ی ک ہ; stray characters from other scripts. Write postpositions as "
    "separate words, for example: اس کی (not اسکی), ان کا (not انکا), جس کے (not "
    "جسکے), کے لیے (not کیلئے or کیلیے). If a sentence contains Devanagari "
    "(Hindi) words, write them in Urdu script. Do NOT change the meaning, the "
    "wording, the order, the numbers, the English words, the emojis, the "
    "markdown (headings, bullets, tables, bold) or any token that looks like "
    "ZX0ZX, ZX1ZX and so on: copy such tokens exactly. Do not translate, do "
    "not add or remove sentences, do not explain anything. If a word is "
    "already correct, keep it exactly. Output only the corrected text."
)


def urdu_ratio(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    arabic = sum(
        1 for c in letters if "\u0600" <= c <= "\u06FF" or "\u0750" <= c <= "\u077F"
    )
    return arabic / len(letters)


def protect_parts(text):
    """Replaces code, formulas and links with tokens so the proofreader cannot touch them."""
    saved = []

    def keep(match):
        saved.append(match.group(0))
        return "ZX%dZX" % (len(saved) - 1)

    return PROTECT.sub(keep, text), saved


def proofread_urdu(text):
    """Second pass: a low-temperature proofreader. Returns the original if anything looks wrong."""
    masked, saved = protect_parts(text)
    proof_messages = [
        {"role": "system", "content": PROOF_SYSTEM},
        {"role": "user", "content": masked},
    ]
    try:
        if prefer_custom():
            result, _ = custom_chat(proof_messages, 0.1)
        elif client is not None:
            result = ask_once(proof_messages, MODEL_NAME, 0.1)
        else:
            return text
    except Exception:
        return text
    result = re.sub(r"(?s)<think>.*?</think>", "", result or "").strip()
    if not result:
        return text
    ratio = len(result) / max(1, len(masked))
    if not 0.7 <= ratio <= 1.3:
        return text
    if abs(result.count("\n") - masked.count("\n")) > 3 + masked.count("\n") * 0.3:
        return text
    for index in range(len(saved)):
        if result.count("ZX%dZX" % index) != 1:
            return text
    for index, original in enumerate(saved):
        result = result.replace("ZX%dZX" % index, original)
    return result


def polish_urdu(text, spell_check=True):
    """Cleans Urdu answers. Returns (text, changed_by_proofreader)."""
    if not text or urdu_ratio(text) < 0.3:
        return text, False
    for bad, good in ARABIC_FIXES.items():
        text = text.replace(bad, good)
    text = STRAY_SCRIPTS.sub("", text)
    if spell_check:
        fixed = proofread_urdu(text)
        return fixed, fixed != text
    return text, False


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
        # Whisper often labels spoken Urdu as Persian, Arabic or Punjabi: try again as Urdu
        if detected in ("persian", "farsi", "arabic", "pashto", "punjabi", "sindhi"):
            retry = client.audio.transcriptions.create(
                model=AUDIO_MODEL,
                file=("voice.wav", audio_bytes),
                temperature=0,
                prompt=HINTS["اردو"],
                language="ur",
            )
            return (retry.text or "").strip()
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
            st.caption("🌐 یہ انٹرنیٹ سے ملی ہوئی اصل تصاویر ہیں، ایپ نے نہیں بنائیں")
            photo_links(photos)
            show_sources(sources, "📎 Sources")
        elif image:
            st.image(image)
            st.caption("🎨 یہ تصویر ایپ نے خود بنائی ہے")
            image_download_button(image, key)
        else:
            st.markdown(text)
            show_sources(sources)


if st.session_state.messages:
    if st.button("🗑 New chat"):
        st.session_state.messages = []
        for key in ("video_id", "video_text", "video_title", "image_info",
                    "reference_info", "reference_task", "chat_summary",
                    "summary_upto", "doc_text"):
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

PATTERN_AFTER = re.compile(
    r"(?i)\b(pattern|same (way|pattern|style|format)|isi (tarah|pattern)|"
    r"next question|agla sawal)\b"
    r"|پیٹرن|اسی (طرح|انداز|طریقے|پیٹرن)|اگلا سوال|पैटर्न|अगला सवाल"
)
IMAGE_TYPES = ["png", "jpg", "jpeg", "jpe", "jfif", "webp", "gif", "bmp", "tif",
               "tiff", "heic", "heif", "avif"]
try:
    prompt = st.chat_input(
        "Ask Quantum",
        accept_audio=True,
        accept_file="multiple",
        file_type=None,
    )
except TypeError:
    try:
        prompt = st.chat_input("Ask Quantum", accept_audio=True)
    except TypeError:
        prompt = st.chat_input("Ask Quantum")

camera_send = bool(send_cam and cam is not None)
upload_send = bool(send_up and up_files)

if prompt or camera_send or upload_send:
    user_text = (getattr(prompt, "text", prompt) if prompt else "") or ""
    files = list(getattr(prompt, "files", None) or []) if prompt else []
    images = []
    if camera_send:
        files = [cam]
        user_text = (cam_text or "").strip()
        st.session_state.cam_n = st.session_state.get("cam_n", 0) + 1
    if up_files and (upload_send or prompt) and not camera_send:
        files = files + list(up_files)
        if not user_text.strip():
            user_text = (up_text or "").strip()
        st.session_state.up_n = st.session_state.get("up_n", 0) + 1

    audio = getattr(prompt, "audio", None) if prompt else None
    if audio and client is None:
        st.warning("مائک سے بولنے کے لیے Groq key درکار ہے (GROQ_API_KEY شامل کریں)۔")
    elif audio:
        try:
            spoken = transcribe(audio.getvalue())
            if spoken is None:
                st.warning(
                    "آواز کی زبان پہچانی نہیں گئی۔ اوپر Mic language میں "
                    "اردو یا English چن کر دوبارہ بولیں۔"
                )
            elif spoken:
                if has_devanagari(spoken):
                    spoken = to_urdu_script(spoken)
                user_text = (user_text + "\n" + spoken).strip()
        except Exception as error:
            st.error("Voice error: " + str(error))

    failed = []
    doc_texts = []
    skipped = 0
    for file in files:
        name = getattr(file, "name", "file")
        ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
        if ext in DOC_TYPES:
            doc = read_document(file.getvalue(), ext)
            if doc:
                doc_texts.append("FILE: " + name + "\n" + doc)
            else:
                failed.append(name)
        elif len(images) < MAX_IMAGES:
            prepared = prepare_image(file.getvalue())
            if prepared:
                images.append(prepared)
            else:
                failed.append(name)
        else:
            skipped += 1
    if doc_texts:
        st.session_state.doc_text = "\n\n".join(doc_texts)[:12000]
    if skipped:
        st.info("ایک وقت میں صرف پہلی %d تصاویر استعمال ہوتی ہیں۔" % MAX_IMAGES)
    if failed:
        st.warning(
            "یہ فائلیں نہیں کھل سکیں: " + "، ".join(failed) + "۔ اگر یہ آئی فون کی "
            "HEIC تصویر ہے تو اسے jpg میں بدل کر بھیجیں۔ اسکین شدہ PDF کا ٹیکسٹ "
            "نہیں پڑھا جا سکتا، اس کی تصویر بھیج دیں۔"
        )
    if files and not images and not doc_texts:
        st.stop()
    if images and not user_text.strip():
        user_text = DEFAULT_IMAGE_QUESTION
    if doc_texts and not user_text.strip():
        user_text = DEFAULT_DOC_QUESTION
    if not user_text.strip():
        st.stop()

    new_message = {"role": "user", "content": user_text}
    if images:
        new_message["images"] = images
    st.session_state.messages.append(new_message)
    show_message("user", user_text, user_images=images)

    if (
        is_image_request(user_text)
        and not find_youtube_id(user_text)
        and not images
        and not doc_texts
    ):
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
                st.caption("🎨 یہ تصویر ایپ نے خود بنائی ہے: " + plan)
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
                st.caption("🌐 یہ انٹرنیٹ سے ملی ہوئی اصل تصاویر ہیں، ایپ نے نہیں بنائیں: " + plan)
                photo_links(photos)
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
                if kind == "PHOTO":
                    st.error("⚠️ تصاویر نہیں مل سکیں: " + str(img_err))
                else:
                    st.error("⚠️ تصویر نہیں بن سکی: (" + str(img_err) + ")")
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
        image_read = ""
        fresh_reference = False
        with text_box:
            with st.spinner("Thinking..."):
                try:
                    extra = ""
                    video_note = ""
                    image_note = ""
                    if (
                        not images
                        and st.session_state.get("image_info")
                        and PATTERN_AFTER.search(user_text)
                    ):
                        st.session_state.reference_info = st.session_state.pop("image_info")
                        st.session_state.reference_task = user_text
                        fresh_reference = True
                        image_note = "📌 Reference example saved"
                    if images:
                        description, vision_error = describe_images(
                            images, user_text
                        ) or ("", "no result")
                        if description:
                            image_read = description
                            if PATTERN_WORDS.search(user_text):
                                st.session_state.reference_info = description
                                st.session_state.reference_task = user_text
                                st.session_state.pop("image_info", None)
                                fresh_reference = True
                                image_note = "📌 Reference example saved"
                            else:
                                st.session_state.image_info = description
                                image_note = "🖼 Image analyzed"
                            if unclear_score(description) >= 3:
                                image_note += " (parts unclear: retake closer, brighter, straighter)"
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
                        transcript, yt_err = youtube_transcript(vid) or (
                            "", "no result returned"
                        )
                        if transcript:
                            st.session_state.video_id = vid
                            st.session_state.video_text = transcript
                            st.session_state.video_title = youtube_title(vid)
                            video_note = "🎬 YouTube transcript loaded"
                        else:
                            video_note = "⚠️ YouTube transcript failed: " + yt_err

                    if vid or images or doc_texts:
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
                    if not query and not qwarn and not vid and not images and not doc_texts:
                        search_note = "ℹ️ No web search for this question"
                    search_note = (
                        video_note + " " + image_note + " " + qwarn + " " + search_note
                    ).strip()

                    has_video = bool(st.session_state.get("video_text"))
                    history_chars = (
                        HISTORY_CHARS_WITH_VIDEO if has_video else HISTORY_CHARS
                    )

                    def attempt(video_limit, hist_chars, summary_chars=900,
                                more="", temp=None):
                        all_messages = st.session_state.messages
                        start = max(
                            st.session_state.get("summary_upto", 0),
                            len(all_messages) - MAX_HISTORY,
                        )
                        history = trim_history(
                            all_messages[min(start, len(all_messages) - 1):], hist_chars
                        )
                        video_text = video_block(video_limit)
                        image_text = image_block(
                            3500 if video_limit >= VIDEO_CTX_CHARS else 1500,
                            fresh_reference,
                        )
                        doc_text = doc_block(9000 if video_limit >= VIDEO_CTX_CHARS else 3000)
                        prefix = "\n\n".join(
                            t for t in (video_text, image_text, doc_text) if t
                        )
                        if prefix and history:
                            last = history[-1]
                            history[-1] = {
                                "role": last["role"],
                                "content": (
                                    prefix + "\n\nUSER MESSAGE:\n" + last["content"]
                                ),
                            }
                        system = system_text + extra + summary_block(summary_chars) + more
                        to_send = [{"role": "system", "content": system}] + history
                        return fix_math(ask_model(to_send, temp or 0.4, custom=use_custom))

                    try:
                        answer = attempt(VIDEO_CTX_CHARS, history_chars)
                    except Exception as first_error:
                        too_big = (
                            "413" in str(first_error)
                            or "too large" in str(first_error).lower()
                        )
                        if not too_big:
                            raise
                        answer = attempt(2500, 1200, 400)
                        search_note = (search_note + " ✂️ Context shortened").strip()

                    custom_error = st.session_state.pop("custom_error", "")
                    if st.session_state.pop("custom_used", False):
                        search_note = (search_note + " 🏠 اپنے سرور سے جواب").strip()
                    elif custom_error:
                        search_note = (
                            search_note + " ↪️ اپنا سرور نہیں ملا، Groq استعمال ہوا ("
                            + custom_error[:80] + ")"
                        ).strip()
                    if st.session_state.pop("used_backup", False):
                        search_note = (
                            search_note + " ↪️ Backup model (main daily limit reached)"
                        ).strip()

                    previous_answer = last_answer_text(st.session_state.messages)
                    if previous_answer and too_similar(answer, previous_answer):
                        try:
                            retry = attempt(
                                VIDEO_CTX_CHARS, history_chars, 900,
                                repeat_warning(previous_answer), 0.9,
                            )
                            if retry.strip() and not too_similar(retry, previous_answer):
                                answer = retry
                                search_note = (
                                    search_note + " 🔁 Avoided repeating the last answer"
                                ).strip()
                        except Exception:
                            pass

                    # Urdu spelling: clean wrong letters, then proofread once
                    answer, proofed = polish_urdu(answer, fix_on)
                    if proofed:
                        search_note = (search_note + " ✍️ اردو املا جانچا گیا").strip()
                except Exception as error:
                    st.session_state.messages.pop()
                    msg = str(error)
                    if "429" in msg or "rate limit" in msg.lower():
                        if "(TPD)" in msg:
                            limit_kind = "روزانہ"
                        elif "(TPM)" in msg:
                            limit_kind = "فی منٹ"
                        else:
                            limit_kind = "روزانہ یا فی منٹ"
                        wait = rate_limit_wait(error)
                        if wait is None:
                            when = "کچھ دیر"
                        elif wait >= 60:
                            when = "تقریباً " + str(int(wait // 60) + 1) + " منٹ"
                        else:
                            when = "تقریباً " + str(int(wait) + 1) + " سیکنڈ"
                        st.error(
                            "⏳ Groq کی " + limit_kind + " مفت حد پوری ہو گئی ہے۔ "
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
                if image_read:
                    with st.expander("🖼 What I read from your photo"):
                        st.text(image_read)
                if video_note.startswith("🎬") and st.session_state.get("video_text"):
                    with st.expander("📄 Video transcript (check names here)"):
                        st.write(st.session_state.video_text)
            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "sources": sources}
            )
            update_summary()
