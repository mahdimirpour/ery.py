import os
import re
from io import BytesIO
from urllib.parse import quote
import concurrent.futures

import requests
from bs4 import BeautifulSoup
from rubka import Robot, Message
from deep_translator import GoogleTranslator

TOKEN = "BICHIA0YKDHSICBQBKGZHBZJAESKOFBNRXUTCEJAIZVLLWCZZETVPFCCJLIMHLJG"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

WIKI_API = "https://fa.wikipedia.org/w/api.php"
WIKI_SUMMARY_API = "https://fa.wikipedia.org/api/rest_v1/page/summary/{}"
DDG_HTML = "https://html.duckduckgo.com/html/"
BING_SEARCH = "https://www.bing.com/search"

bot = Robot(token=TOKEN, web_hook="")

# ذخیره وضعیت کاربران
USER_STATE = {}

# -------------------- Safety / Content Filter --------------------

BANNED_PATTERNS = [
    r"\bsex\b", r"\bsexy\b", r"\bporn\b", r"\bxxx\b", r"\bfuck\b",
    r"\bblowjob\b", r"\bbj\b", r"\bdick\b", r"\bpussy\b", r"\bhorny\b",
    r"\bnude\b", r"\bnaked\b", r"\b18\+\b", r"\bسکس\b", r"\bسکسی\b",
    r"\bپورن\b", r"\bلخت\b", r"\bبرهنه\b",
]

def contains_banned_content(text: str) -> bool:
    text = text or ""
    for pattern in BANNED_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def refusal_text():
    return "در این مورد نمی‌توانم کمک کنم."

# -------------------- Utils --------------------

def clean_text(text: str) -> str:
    text = re.sub(r"\[\d+\]", "", text or "")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()

def get_state(chat_id):
    if chat_id not in USER_STATE:
        USER_STATE[chat_id] = {
            "mode": None,
            "waiting": False,
            "awaiting_lang": False,
            "translate_target": None
        }
    return USER_STATE[chat_id]

def set_state(chat_id, **kwargs):
    if chat_id not in USER_STATE:
        USER_STATE[chat_id] = {
            "mode": None,
            "waiting": False,
            "awaiting_lang": False,
            "translate_target": None
        }
    for key, value in kwargs.items():
        if key in USER_STATE[chat_id]:
            USER_STATE[chat_id][key] = value

def normalize_cmd(text: str) -> str:
    return (text or "").strip().lower()

def detect_language_code(text: str) -> str | None:
    t = normalize_cmd(text)
    mapping = {
        "fa": "fa", "farsi": "fa", "persian": "fa", "فارسی": "fa",
        "انگلیسی": "en", "english": "en", "en": "en",
        "arabic": "ar", "عربی": "ar", "ar": "ar",
        "turkish": "tr", "ترکی": "tr", "tr": "tr",
        "german": "de", "آلمانی": "de", "de": "de",
        "french": "fr", "فرانسوی": "fr", "fr": "fr",
        "russian": "ru", "روسی": "ru", "ru": "ru",
        "spanish": "es", "اسپانیایی": "es", "es": "es",
        "italian": "it", "ایتالیایی": "it", "it": "it",
    }
    return mapping.get(t)

# -------------------- Safe Send --------------------

async def safe_reply(message: Message, text: str, **kwargs):
    try:
        return await message.reply(text, **kwargs)
    except Exception as e:
        print("reply error:", e)
        return None

async def safe_delete(msg):
    try:
        if msg:
            await msg.delete()
    except Exception as e:
        print("delete error:", e)

# -------------------- Translation --------------------

async def translate_text(text: str, target_lang: str) -> str:
    """ترجمه با استفاده از Google Translate"""
    try:
        text = clean_text(text)
        if not text:
            return "متنی برای ترجمه ارسال نشده."
        
        if contains_banned_content(text):
            return refusal_text()
        
        translator = GoogleTranslator(target=target_lang)
        result = translator.translate(text)
        return clean_text(result)
        
    except Exception as e:
        print(f"Translation error: {e}")
        return f"❌ خطا در ترجمه: {str(e)}"

# -------------------- Search Functions --------------------

def search_wikipedia(query: str):
    """جستجو در ویکی‌پدیا - اولویت اول"""
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1,
            "srlimit": 1,
        }
        response = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=8)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("query", {}).get("search", [])
        if not results:
            return None
        
        title = results[0].get("title")
        url = WIKI_SUMMARY_API.format(quote(title.replace(" ", "_")))
        
        response = requests.get(url, headers=HEADERS, timeout=8)
        response.raise_for_status()
        data = response.json()
        
        extract = data.get("extract")
        if extract:
            return clean_text(extract)
        return None
        
    except Exception as e:
        print(f"Wikipedia error: {e}")
        return None

def search_duckduckgo(query: str):
    """جستجو در DuckDuckGo - منبع دوم"""
    try:
        params = {"q": query}
        response = requests.get(DDG_HTML, params=params, headers=HEADERS, timeout=8)
        response.raise_for_status()
        html = response.text
        
        soup = BeautifulSoup(html, "html.parser")
        items = []
        
        for result in soup.select(".result")[:2]:
            title_el = result.select_one(".result__title a")
            snippet_el = result.select_one(".result__snippet")
            
            if not title_el:
                continue
            
            title = clean_text(title_el.get_text(" ", strip=True))
            snippet = clean_text(snippet_el.get_text(" ", strip=True)) if snippet_el else ""
            
            items.append(f"{title}\n{snippet}")
        
        if items:
            return "\n\n".join(items[:2])
        return None
        
    except Exception as e:
        print(f"DuckDuckGo error: {e}")
        return None

def search_bing(query: str):
    """جستجو در Bing - منبع سوم"""
    try:
        params = {"q": query, "count": 3}
        response = requests.get(BING_SEARCH, params=params, headers=HEADERS, timeout=8)
        response.raise_for_status()
        html = response.text
        
        soup = BeautifulSoup(html, "html.parser")
        items = []
        
        for result in soup.select("#b_results .b_algo")[:2]:
            title_el = result.select_one("h2 a")
            if not title_el:
                continue
            
            title = clean_text(title_el.get_text(" ", strip=True))
            snippet_el = result.select_one(".b_caption p")
            snippet = clean_text(snippet_el.get_text(" ", strip=True)) if snippet_el else ""
            
            items.append(f"{title}\n{snippet}")
        
        if items:
            return "\n\n".join(items[:2])
        return None
        
    except Exception as e:
        print(f"Bing error: {e}")
        return None

def search_all_sources(query: str, mode: str = "full") -> str:
    """جستجو با اولویت ویکی‌پدیا و سپس منابع دیگر"""
    query = clean_text(query)
    if not query:
        return "متنی برای پردازش ارسال نشده."
    
    if contains_banned_content(query):
        return refusal_text()
    
    # مرحله 1: اول ویکی‌پدیا رو چک کن
    wiki_result = search_wikipedia(query)
    if wiki_result:
        # اگر ویکی نتیجه داشت، همون رو برگردون
        if mode == "short":
            if len(wiki_result) > 500:
                return wiki_result[:500] + "..."
            return wiki_result
        return wiki_result
    
    # مرحله 2: اگر ویکی نتیجه نداشت، برو سراغ منابع دیگه
    ddg_result = search_duckduckgo(query)
    bing_result = search_bing(query)
    
    # ترکیب نتایج از منابع دیگه
    results = []
    if ddg_result:
        results.append(ddg_result)
    if bing_result:
        results.append(bing_result)
    
    if not results:
        return "❌ نتیجه‌ای برای جستجوی شما پیدا نشد."
    
    # ادغام نتایج
    final_result = "\n\n" + "─" * 40 + "\n\n".join(results)
    
    # اگر حالت خلاصه بود
    if mode == "short":
        if len(final_result) > 700:
            return final_result[:700] + "..."
    
    return final_result

# -------------------- Image Helpers --------------------

def extract_string_reference(obj):
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj.strip() or None
    if isinstance(obj, list):
        for item in obj:
            ref = extract_string_reference(item)
            if ref:
                return ref
        return None
    if isinstance(obj, dict):
        for key in ("url", "file_url", "download_url", "src", "path", "link"):
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in obj.values():
            ref = extract_string_reference(value)
            if ref:
                return ref
        return None
    for attr in ("url", "file_url", "download_url", "src", "path", "link"):
        if hasattr(obj, attr):
            value = getattr(obj, attr)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if hasattr(obj, "__dict__"):
        return extract_string_reference(getattr(obj, "__dict__"))
    return None

def get_image_reference(message: Message):
    for field in ("photo", "image", "file", "attachment", "media", "document", "content"):
        if hasattr(message, field):
            ref = extract_string_reference(getattr(message, field))
            if ref:
                return ref
    for field in ("data", "payload", "__dict__"):
        if hasattr(message, field):
            ref = extract_string_reference(getattr(message, field))
            if ref:
                return ref
    return None

def download_bytes(ref: str):
    if not ref:
        return None
    if os.path.exists(ref):
        with open(ref, "rb") as f:
            return f.read()
    if ref.startswith("http://") or ref.startswith("https://"):
        response = requests.get(ref, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return response.content
    return None

def ocr_image_bytes(image_bytes: bytes) -> str:
    try:
        from PIL import Image
        import pytesseract
        img = Image.open(BytesIO(image_bytes))
        text = pytesseract.image_to_string(img, lang="fas+eng")
        return clean_text(text)
    except Exception as e:
        print("ocr error:", e)
        return ""

async def build_image_response(message: Message) -> str:
    image_ref = get_image_reference(message)
    if not image_ref:
        return "❌ عکس پیدا نشد. دوباره عکس را ارسال کن."
    
    image_bytes = download_bytes(image_ref)
    if not image_bytes:
        return "❌ نتوانستم فایل عکس را دریافت کنم."
    
    extracted_text = ocr_image_bytes(image_bytes)
    if not extracted_text:
        return "❌ از داخل عکس متن قابل خواندن پیدا نشد."
    
    if contains_banned_content(extracted_text):
        return refusal_text()
    
    state = get_state(getattr(message, "chat_id", None))
    if state.get("mode") == "translate" and state.get("translate_target"):
        translated = await translate_text(extracted_text, state["translate_target"])
        return f"📝 **متن تشخیص داده شده:**\n{extracted_text}\n\n🌐 **ترجمه:**\n{translated}"
    
    answer = search_all_sources(extracted_text, mode="full")
    return f"📝 **متن تشخیص داده شده:**\n{extracted_text}\n\n{answer}"

# -------------------- Menus --------------------

def settings_menu_text():
    return (
        "📋 **منوی تنظیمات:**\n\n"
        "1️⃣ **سرچ کامل** - جستجو از همه منابع\n"
        "2️⃣ **سرچ خلاصه** - نتیجه مختصر\n"
        "3️⃣ **جستجوی تصویری** - OCR از عکس\n"
        "4️⃣ **ترجمه متن** - ترجمه با گوگل\n"
        "5️⃣ **لغو حالت** - بازگشت به حالت عادی\n\n"
        "عدد گزینه یا اسم آن را بفرست."
    )

def translate_menu_text():
    return (
        "🌐 **ترجمه فعال شد.**\n\n"
        "می‌خوای به چه زبانی ترجمه بشه؟\n"
        "مثال: فارسی، انگلیسی، عربی، ترکی، آلمانی\n\n"
        "📌 زبان‌های پشتیبانی شده:\n"
        "فارسی، انگلیسی، عربی، ترکی، آلمانی، فرانسوی، روسی، اسپانیایی، ایتالیایی"
    )

# -------------------- Commands --------------------

@bot.on_message(commands=["start"])
async def start(bot: Robot, message: Message):
    chat_id = getattr(message, "chat_id", None)
    if chat_id is not None:
        set_state(chat_id, mode=None, waiting=False, awaiting_lang=False, translate_target=None)
    
    await safe_reply(
        message,
        "✅ **سلام! خوش اومدی.**\n\n"
        "📌 **برای استفاده بهتر از ربات، عضو کانال سازنده شوید:**\n"
        "https://rubika.ir/join/Meta_web\n\n"
        "💡 **موضوعت را بفرست تا برات جستجو کنم.**\n"
        "🔍 **اولویت جستجو:** ویکی‌پدیا → DuckDuckGo → Bing\n"
        "🌐 **ترجمه:** Google Translate\n\n"
        "📋 **برای تنظیمات:** /setting"
    )

@bot.on_message(commands=["setting"])
async def settings(bot: Robot, message: Message):
    chat_id = getattr(message, "chat_id", None)
    if chat_id is None:
        return
    
    set_state(chat_id, mode="menu", waiting=True, awaiting_lang=False, translate_target=None)
    await safe_reply(message, settings_menu_text())

# -------------------- Main Message Handler --------------------

@bot.on_message()
async def handle_messages(bot: Robot, message: Message):
    try:
        chat_id = getattr(message, "chat_id", None)
        if chat_id is None:
            return

        text = (getattr(message, "text", "") or "").strip()
        caption = (getattr(message, "caption", "") or "").strip()
        content = text or caption

        if not content and not get_image_reference(message):
            return

        lowered = normalize_cmd(content)

        if lowered == "/start" or lowered == "/setting":
            return

        state = get_state(chat_id)

        # اگر حالت ترجمه و منتظر زبان است
        if state.get("mode") == "translate" and state.get("awaiting_lang"):
            lang_code = detect_language_code(content)
            if not lang_code:
                await safe_reply(
                    message,
                    "❌ **زبان را درست بفرست.**\n"
                    "مثال: فارسی، انگلیسی، عربی، ترکی، آلمانی\n\n"
                    "📌 زبان‌های پشتیبانی شده:\n"
                    "فارسی، انگلیسی، عربی، ترکی، آلمانی، فرانسوی، روسی، اسپانیایی، ایتالیایی"
                )
                return

            set_state(chat_id, mode="translate", waiting=True, awaiting_lang=False, translate_target=lang_code)
            await safe_reply(
                message,
                f"✅ **زبان ترجمه روی {lang_code} تنظیم شد.**\n"
                f"حالا متن را بفرست تا ترجمه کنم."
            )
            return

        # اگر در منو است
        if state.get("mode") == "menu" or (state.get("waiting") and state.get("mode") is None):
            if lowered in ("1", "سرچ کامل", "کامل", "full"):
                set_state(chat_id, mode="full", waiting=True, awaiting_lang=False, translate_target=None)
                await safe_reply(message, "✅ **حالت سرچ کامل فعال شد.**\nموضوع را بفرست تا جستجو کنم.")
                return

            if lowered in ("2", "سرچ خلاصه", "خلاصه", "short"):
                set_state(chat_id, mode="short", waiting=True, awaiting_lang=False, translate_target=None)
                await safe_reply(message, "✅ **حالت سرچ خلاصه فعال شد.**\nموضوع را بفرست تا نتیجه مختصر بگیرم.")
                return

            if lowered in ("3", "جستجوی تصویری", "تصویری", "image"):
                set_state(chat_id, mode="image", waiting=True, awaiting_lang=False, translate_target=None)
                await safe_reply(message, "✅ **حالت جستجوی تصویری فعال شد.**\nعکس را بفرست تا متن داخلش رو بخونم.")
                return

            if lowered in ("4", "ترجمه متن", "ترجمه", "translate"):
                set_state(chat_id, mode="translate", waiting=True, awaiting_lang=True, translate_target=None)
                await safe_reply(message, translate_menu_text())
                return

            if lowered in ("5", "لغو", "cancel", "off", "خاموش"):
                set_state(chat_id, mode=None, waiting=False, awaiting_lang=False, translate_target=None)
                await safe_reply(message, "✅ **حالت فعلی لغو شد.**")
                return

            # اگر گزینه نامعتبر بود، منو را دوباره نشان بده
            await safe_reply(message, settings_menu_text())
            return

        # فیلتر محتوای نامناسب
        if contains_banned_content(content):
            await safe_reply(message, refusal_text())
            return

        mode = state.get("mode")

        # حالت ترجمه
        if mode == "translate":
            target_lang = state.get("translate_target")
            if not target_lang:
                set_state(chat_id, mode="translate", waiting=True, awaiting_lang=True, translate_target=None)
                await safe_reply(message, translate_menu_text())
                return

            processing_msg = await safe_reply(message, "⏳ **درحال ترجمه...**")
            try:
                translated = await translate_text(content, target_lang)
                await safe_reply(message, f"🌐 **ترجمه به {target_lang}:**\n\n{translated}")
            finally:
                await safe_delete(processing_msg)
            return

        # حالت سرچ کامل یا خلاصه
        if mode in ("full", "short"):
            processing_msg = await safe_reply(message, "⏳ **درحال جستجو...**")
            try:
                answer = search_all_sources(content, mode=mode)
                await safe_reply(message, answer)
            finally:
                await safe_delete(processing_msg)
            return

        # حالت تصویری
        if mode == "image":
            processing_msg = await safe_reply(message, "⏳ **درحال پردازش عکس...**")
            try:
                image_ref = get_image_reference(message)
                if image_ref:
                    answer = await build_image_response(message)
                    await safe_reply(message, answer)
                elif content:
                    answer = search_all_sources(content, mode="full")
                    await safe_reply(message, answer)
                else:
                    await safe_reply(message, "❌ **عکس را بفرست.**")
            finally:
                await safe_delete(processing_msg)
            return

        # حالت پیش‌فرض - جستجو با اولویت ویکی
        processing_msg = await safe_reply(message, "⏳ **درحال جستجو...**")
        try:
            answer = search_all_sources(content, mode="full")
            await safe_reply(message, answer)
        finally:
            await safe_delete(processing_msg)

    except Exception as e:
        print(f"message handler error: {e}")
        await safe_reply(message, f"❌ **خطایی رخ داد:** {str(e)}")

if __name__ == "__main__":
    print("ربات راه‌اندازی شد...")
    print("اولویت جستجو: Wikipedia → DuckDuckGo → Bing")
    print("ترجمه: Google Translate")
    bot.run()
