import os
import re
import json
import time
from io import BytesIO
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

TOKEN = "TOKEN_BIT"
BASE_URL = "https://rubika.ir/api/v1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json"
}

# -------------------- API Functions --------------------

def send_message(chat_id, text):
    """ارسال پیام با API مستقیم روبیکا"""
    url = f"{BASE_URL}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        response = requests.post(url, json=data, headers=HEADERS, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Send error: {e}")
        return None

def get_updates(offset=0):
    """دریافت پیام‌های جدید"""
    url = f"{BASE_URL}/getUpdates"
    params = {"offset": offset, "timeout": 30}
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=35)
        return response.json()
    except Exception as e:
        print(f"Updates error: {e}")
        return {"ok": False, "result": []}

# -------------------- Search Functions --------------------

def search_wikipedia(query):
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1,
            "srlimit": 1,
        }
        response = requests.get("https://fa.wikipedia.org/w/api.php", params=params, timeout=8)
        data = response.json()
        results = data.get("query", {}).get("search", [])
        if not results:
            return None
        title = results[0].get("title")
        url = f"https://fa.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}"
        response = requests.get(url, timeout=8)
        data = response.json()
        return clean_text(data.get("extract", ""))
    except:
        return None

def search_duckduckgo(query):
    try:
        params = {"q": query}
        response = requests.get("https://html.duckduckgo.com/html/", params=params, timeout=8)
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        for result in soup.select(".result")[:2]:
            title_el = result.select_one(".result__title a")
            if not title_el:
                continue
            snippet_el = result.select_one(".result__snippet")
            title = clean_text(title_el.get_text(" ", strip=True))
            snippet = clean_text(snippet_el.get_text(" ", strip=True)) if snippet_el else ""
            items.append(f"{title}\n{snippet}")
        return "\n\n".join(items[:2]) if items else None
    except:
        return None

def search_bing(query):
    try:
        params = {"q": query, "count": 3}
        response = requests.get("https://www.bing.com/search", params=params, timeout=8)
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        for result in soup.select("#b_results .b_algo")[:2]:
            title_el = result.select_one("h2 a")
            if not title_el:
                continue
            title = clean_text(title_el.get_text(" ", strip=True))
            snippet_el = result.select_one(".b_caption p")
            snippet = clean_text(snippet_el.get_text(" ", strip=True)) if snippet_el else ""
            items.append(f"{title}\n{snippet}")
        return "\n\n".join(items[:2]) if items else None
    except:
        return None

def search_all_sources(query):
    query = clean_text(query)
    if not query:
        return "متنی برای پردازش ارسال نشده."
    
    wiki_result = search_wikipedia(query)
    if wiki_result:
        return wiki_result
    
    ddg_result = search_duckduckgo(query)
    bing_result = search_bing(query)
    
    results = []
    if ddg_result:
        results.append(ddg_result)
    if bing_result:
        results.append(bing_result)
    
    if not results:
        return "❌ نتیجه‌ای پیدا نشد."
    
    return "\n\n" + "─" * 40 + "\n\n".join(results)

def translate_text(text, target_lang):
    try:
        translator = GoogleTranslator(target=target_lang)
        return translator.translate(text)
    except:
        return "❌ خطا در ترجمه"

def clean_text(text):
    text = re.sub(r"\[\d+\]", "", text or "")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()

# -------------------- Main Loop --------------------

def main():
    print("ربات راه‌اندازی شد...")
    offset = 0
    user_state = {}
    
    while True:
        try:
            updates = get_updates(offset)
            if not updates.get("ok"):
                time.sleep(5)
                continue
            
            for result in updates.get("result", []):
                offset = result.get("update_id", 0) + 1
                message = result.get("message", {})
                chat_id = message.get("chat_id")
                text = message.get("text", "").strip()
                
                if not chat_id:
                    continue
                
                # پردازش پیام
                if text == "/start":
                    send_message(chat_id, 
                        "✅ سلام! خوش اومدی.\n\n"
                        "📌 برای استفاده بهتر از ربات، عضو کانال سازنده شوید:\n"
                        "https://rubika.ir/join/Meta_web\n\n"
                        "💡 موضوعت را بفرست تا برات جستجو کنم."
                    )
                else:
                    send_message(chat_id, "⏳ درحال جستجو...")
                    result = search_all_sources(text)
                    send_message(chat_id, result)
            
        except Exception as e:
            print(f"Main error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
