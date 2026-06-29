import re
import time
import asyncio
import requests
from urllib.parse import quote
from rubka import Robot, Message

# ==================== توکن‌ها ====================
TOKEN = "BICHIA0YKDHSICBQBKGZHBZJAESKOFBNRXUTCEJAIZVLLWCZZETVPFCCJLIMHLJG"
GROQ_API_KEY = "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"

# ==================== آیدی ادمین ====================
ADMIN_ID = "b0HZHuj0o22032ecfc4d2e1b44ef6f49"

# ==================== تنظیمات Groq ====================
API_URL = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

bot = Robot(token=TOKEN, web_hook="")
USER_STATS = {}

# ==================== تابع Groq با مدیریت خطا ====================

def ask_groq(question):
    try:
        data = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": "پاسخ مختصر و مفید به فارسی."},
                {"role": "user", "content": question}
            ],
            "max_tokens": 300,
            "temperature": 0.5
        }

        response = requests.post(API_URL, json=data, headers=HEADERS, timeout=5)

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"][:500]

        elif response.status_code == 502:
            return "❌ خطای ۵۰۲ (Bad Gateway): سرور Groq در دسترس نیست. چند دقیقه بعد تلاش کن."

        elif response.status_code == 401:
            return "❌ کلید API نامعتبر است. از پنل Groq کلید جدید بگیر."

        elif response.status_code == 429:
            return "⏳ محدودیت درخواست. ۵ ثانیه صبر کن."

        else:
            return f"❌ خطا: {response.status_code}"

    except requests.exceptions.Timeout:
        return "⏰ زمان پاسخ بیشتر از حد مجاز بود."
    except Exception as e:
        return f"❌ خطا: {str(e)[:100]}"

# ==================== جستجوی ویکی‌پدیا ====================

def search_wikipedia_fast(query):
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1,
            "srlimit": 1,
        }
        response = requests.get("https://fa.wikipedia.org/w/api.php", params=params, timeout=2)
        data = response.json()

        results = data.get("query", {}).get("search", [])
        if not results:
            return None

        title = results[0].get("title")
        url = f"https://fa.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}"
        response = requests.get(url, timeout=2)
        data = response.json()

        extract = data.get("extract")
        if extract:
            text = re.sub(r"\[\d+\]", "", extract)
            text = re.sub(r"\s+", " ", text)
            return text[:500] + "..." if len(text) > 500 else text
        return None
    except:
        return None

# ==================== پردازش پیام ====================

async def process_message(bot, message):
    try:
        chat_id = message.chat_id
        text = message.text or ""

        if not text or text.startswith("/"):
            return

        if chat_id not in USER_STATS:
            USER_STATS[chat_id] = {"messages": 0, "last_active": time.time()}
        USER_STATS[chat_id]["messages"] += 1
        USER_STATS[chat_id]["last_active"] = time.time()

        status_msg = await message.reply("⏳ **در حال اجرا...**")

        response = await asyncio.get_event_loop().run_in_executor(None, ask_groq, text)

        await status_msg.delete()
        await message.reply(f"🤖 {response}")

    except Exception as e:
        print(f"Process error: {e}")
        try:
            await status_msg.delete()
            await message.reply("❌ خطا! دوباره تلاش کن.")
        except:
            pass

# ==================== هندلرها ====================

@bot.on_message(commands=["start"])
async def start(bot, message: Message):
    await message.reply(
        "⚡ **ربات Groq**\n\n"
        f"👤 {'✅ ادمین' if str(message.chat_id) == ADMIN_ID else 'کاربر عادی'}\n\n"
        "💬 هر سوالی بپرس\n"
        "📌 `/wiki موضوع` - ویکی‌پدیا\n"
        "📌 `/admin` - پنل ادمین\n"
        "📌 `/getid` - دریافت آیدی"
    )

@bot.on_message(commands=["getid"])
async def get_id(bot, message: Message):
    await message.reply(f"🆔 **آیدی شما:** `{message.chat_id}`")

@bot.on_message(commands=["admin"])
async def admin_panel(bot, message: Message):
    if str(message.chat_id) != ADMIN_ID:
        await message.reply("❌ فقط ادمین دسترسی دارد.")
        return

    stats = {
        "users": len(USER_STATS),
        "msgs": sum(s.get("messages", 0) for s in USER_STATS.values()),
        "active": len([u for u, s in USER_STATS.items() if s.get("last_active", 0) > time.time() - 3600])
    }

    await message.reply(
        f"🔐 **پنل ادمین**\n\n"
        f"👥 کاربران: {stats['users']}\n"
        f"💬 پیام‌ها: {stats['msgs']}\n"
        f"🟢 آنلاین (۱h): {stats['active']}\n\n"
        "📋 `/stats` - آمار\n"
        "📋 `/users` - لیست کاربران\n"
        "📋 `/broadcast پیام` - ارسال همگانی"
    )

@bot.on_message(commands=["stats"])
async def stats(bot, message: Message):
    if str(message.chat_id) != ADMIN_ID:
        return

    stats = {
        "users": len(USER_STATS),
        "msgs": sum(s.get("messages", 0) for s in USER_STATS.values()),
        "active": len([u for u, s in USER_STATS.items() if s.get("last_active", 0) > time.time() - 3600])
    }

    recent = sorted(USER_STATS.items(), key=lambda x: x[1].get("last_active", 0), reverse=True)[:5]
    recent_text = "\n".join([f"• {uid}: {s.get('messages', 0)} پیام" for uid, s in recent])

    await message.reply(
        f"📊 **آمار لحظه‌ای**\n\n"
        f"👥 کل: {stats['users']}\n"
        f"💬 کل پیام‌ها: {stats['msgs']}\n"
        f"🟢 آنلاین (۱h): {stats['active']}\n\n"
        f"📌 ۵ کاربر آخر:\n{recent_text or 'هیچ'}"
    )

@bot.on_message(commands=["users"])
async def list_users(bot, message: Message):
    if str(message.chat_id) != ADMIN_ID:
        return

    if not USER_STATS:
        await message.reply("📭 هیچ کاربری وجود ندارد.")
        return

    user_list = "\n".join([f"• {uid}: {s.get('messages', 0)} پیام" for uid, s in USER_STATS.items()])

    if len(user_list) > 4000:
        for i in range(0, len(user_list), 4000):
            await message.reply(f"👥 کاربران:\n\n{user_list[i:i+4000]}")
    else:
        await message.reply(f"👥 کاربران ({len(USER_STATS)} نفر):\n\n{user_list}")

@bot.on_message(commands=["broadcast"])
async def broadcast(bot, message: Message):
    if str(message.chat_id) != ADMIN_ID:
        return

    text = message.text or ""
    parts = text.split(" ", 1)
    if len(parts) < 2:
        await message.reply("❌ `/broadcast پیام`")
        return

    broadcast_text = parts[1].strip()
    status_msg = await message.reply(f"⏳ ارسال به {len(USER_STATS)} کاربر...")

    success = 0
    for user_id in USER_STATS.keys():
        try:
            await bot.send_message(chat_id=user_id, text=f"📢 **پیام همگانی:**\n\n{broadcast_text}")
            success += 1
            await asyncio.sleep(0.05)
        except:
            pass

    await status_msg.delete()
    await message.reply(f"✅ ارسال شد! موفق: {success}")

@bot.on_message(commands=["wiki"])
async def wiki_search(bot, message: Message):
    text = message.text or ""
    parts = text.split(" ", 1)
    if len(parts) < 2:
        await message.reply("❌ `/wiki موضوع`")
        return

    query = parts[1].strip()
    status_msg = await message.reply("⏳ جستجو...")

    result = search_wikipedia_fast(query)
    await status_msg.delete()

    if result:
        await message.reply(f"📚 {result}")
    else:
        await message.reply("❌ نتیجه‌ای پیدا نشد.")

@bot.on_message(commands=["clear"])
async def clear_history(bot, message: Message):
    await message.reply("🗑️ تاریخچه شما پاک شد.")

# ==================== هندلر اصلی ====================

@bot.on_message()
async def handle_messages(bot, message: Message):
    asyncio.create_task(process_message(bot, message))

# ==================== اجرا ====================

if __name__ == "__main__":
    print("🚀 ربات با Groq آنلاین شد.")
    print(f"👤 ادمین: {ADMIN_ID}")
    print("⏳ منتظر پیام‌ها هستم...")
    bot.run()
