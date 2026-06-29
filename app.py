import os
import re
import time
import json
from io import BytesIO
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

TOKEN = "BICHIA0YKDHSICBQBKGZHBZJAESKOFBNRXUTCEJAIZVLLWCZZETVPFCCJLIMHLJG"
BASE_URL = "https://rubika.ir/api/v1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json"
}

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
    return "❌ در این مورد نمی‌توانم کمک کنم."

# -------------------- Utils --------------------

def clean_text(text: str) -> str:
    text = re.sub(r"\[\d+\]", "", text or "")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()

# -------------------- API Functions --------------------

def send_message(chat_id, text):
    """ارسال پیام با API روبیکا"""
    try:
        url = f"{BASE_URL}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text
        }
        response = requests.post(url, json=data, headers=HEADERS, timeout=5)
        return response.json()
    except Exception as e:
        print(f"Send error: {e}")
        return None

def get_updates(offset=0):
    """دریافت پیام‌های جدید با timeout کم"""
    try:
        url = f"{BASE_URL}/getUpdates"
        params = {"offset": offset, "timeout": 1}  # ← timeout 1 ثانیه
        response = requests.get(url, params=params, headers=HEADERS, timeout=2)
        return response.json()
    except Exception as e:
        print(f"Updates error: {e}")
        return {"ok": False, "result": []}

# -------------------- Search Functions --------------------

def search_wikipedia(query):
    """جستجو در ویکی‌پدیا"""
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1,
            "srlimit": 1,
        }
        response = requests.get("https://fa.wikipedia.org/w/api.php", params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("query", {}).get("search", [])
        if not results:
            return None
        
        title = results[0].get("title")
        url = f"https://fa.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        extract = data.get("extract")
        if extract:
            return clean_text(extract)
        return None
    except Exception as e:
        print(f"Wikipedia error: {e}")
        return None

def search_duckduckgo(query):
    """جستجو در DuckDuckGo"""
    try:
        params = {"q": query}
        response = requests.get("https://html.duckduckgo.com/html/", params=params, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        
        for result in soup.select(".result")[:2]:
            title_el = result.select_one(".result__title a")
            if not title_el:
                continue
            title = clean_text(title_el.get_text(" ", strip=True))
            snippet_el = result.select_one(".result__snippet")
            snippet = clean_text(snippet_el.get_text(" ", strip=True)) if snippet_el else ""
            items.append(f"• **{title}**\n{snippet}")
        
        if items:
            return "\n\n".join(items[:2])
        return None
    except Exception as e:
        print(f"DuckDuckGo error: {e}")
        return None

def search_bing(query):
    """جستجو در Bing"""
    try:
        params = {"q": query, "count": 3}
        response = requests.get("https://www.bing.com/search", params=params, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        
        for result in soup.select("#b_results .b_algo")[:2]:
            title_el = result.select_one("h2 a")
            if not title_el:
                continue
            title = clean_text(title_el.get_text(" ", strip=True))
            snippet_el = result.select_one(".b_caption p")
            snippet = clean_text(snippet_el.get_text(" ", strip=True)) if snippet_el else ""
            items.append(f"• **{title}**\n{snippet}")
        
        if items:
            return "\n\n".join(items[:2])
        return None
    except Exception as e:
        print(f"Bing error: {e}")
        return None

def search_all_sources(query, mode="full"):
    """جستجو با اولویت ویکی‌پدیا"""
    query = clean_text(query)
    if not query:
        return "متنی برای پردازش ارسال نشده."
    
    if contains_banned_content(query):
        return refusal_text()
    
    # اولویت با ویکی‌پدیا
    wiki_result = search_wikipedia(query)
    if wiki_result:
        if mode == "short" and len(wiki_result) > 500:
            return wiki_result[:500] + "..."
        return wiki_result
    
    # اگر ویکی نبود، برو سراغ منابع دیگه
    ddg_result = search_duckduckgo(query)
    bing_result = search_bing(query)
    
    results = []
    if ddg_result:
        results.append(ddg_result)
    if bing_result:
        results.append(bing_result)
    
    if not results:
        return "❌ نتیجه‌ای برای جستجوی شما پیدا نشد."
    
    final_result = "\n\n" + "─" * 40 + "\n\n".join(results)
    if mode == "short" and len(final_result) > 700:
        return final_result[:700] + "..."
    
    return final_result

# -------------------- Translation --------------------

def translate_text(text, target_lang):
    """ترجمه با Google Translate"""
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

# -------------------- Main Loop (Polling - 1 Second) --------------------

def main():
    """حلقه اصلی ربات با چک ۱ ثانیه‌ای"""
    print("🤖 ربات راه‌اندازی شد...")
    print("🔍 اولویت جستجو: Wikipedia → DuckDuckGo → Bing")
    print("🌐 ترجمه: Google Translate")
    print("⏳ چک کردن پیام‌ها هر ۱ ثانیه...")
    
    offset = 0
    
    while True:
        try:
            # دریافت پیام‌های جدید با timeout 1 ثانیه
            updates = get_updates(offset)
            
            if updates.get("ok"):
                for result in updates.get("result", []):
                    # بروزرسانی offset
                    update_id = result.get("update_id", 0)
                    if update_id >= offset:
                        offset = update_id + 1
                    
                    # استخراج پیام
                    message = result.get("message", {})
                    chat_id = message.get("chat_id")
                    text = message.get("text", "").strip()
                    
                    if not chat_id or not text:
                        continue
                    
                    print(f"📩 پیام از {chat_id}: {text[:50]}...")
                    
                    # پردازش دستور start
                    if text == "/start":
                        send_message(
                            chat_id,
                            "✅ **سلام! خوش اومدی.**\n\n"
                            "📌 **برای استفاده بهتر از ربات، عضو کانال سازنده شوید:**\n"
                            "https://rubika.ir/join/Meta_web\n\n"
                            "💡 **موضوعت را بفرست تا برات جستجو کنم.**\n"
                            "🔍 **اولویت جستجو:** ویکی‌پدیا → DuckDuckGo → Bing\n"
                            "🌐 **ترجمه:** Google Translate"
                        )
                        continue
                    
                    # پردازش دستور translate
                    if text.startswith("/translate"):
                        parts = text.split(" ", 2)
                        if len(parts) >= 3:
                            lang = parts[1]
                            text_to_translate = parts[2]
                            send_message(chat_id, "⏳ **درحال ترجمه...**")
                            translated = translate_text(text_to_translate, lang)
                            send_message(chat_id, f"🌐 **ترجمه به {lang}:**\n\n{translated}")
                        else:
                            send_message(chat_id, "❌ **استفاده:** `/translate fa متن`")
                        continue
                    
                    # جستجوی عادی
                    send_message(chat_id, "⏳ **درحال جستجو...**")
                    result = search_all_sources(text, mode="full")
                    
                    # اگر نتیجه طولانی بود، تکه تکه بفرست
                    if len(result) > 4000:
                        for i in range(0, len(result), 4000):
                            send_message(chat_id, result[i:i+4000])
                    else:
                        send_message(chat_id, result)
            
            # خواب ۱ ثانیه‌ای (برای جلوگیری از مصرف زیاد CPU)
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Main error: {e}")
            time.sleep(1)

# برای اجرا در پارس‌پک
if __name__ == "__main__":
    main()
