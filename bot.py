# PS.PC — PSN OFFLINE kanalidan yangi postlarni ko'chirish (GitHub Actions uchun)
import os, re, asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION = os.environ["SESSION"]
SOURCE = int(os.environ.get("SOURCE", "-1002567127698"))  # PSN OFFLINE
TARGET = os.environ["TARGET"]                              # @sizning_kanalingiz
CONTACT = os.environ.get("CONTACT", "📩 Buyurtma uchun: @PSPC_admin")
ADD_USD = float(os.environ.get("ADD_USD", "40"))
STATE = "last_id.txt"

PRICE_RE = re.compile(
    r'(?P<pre>\$\s?)(?P<a>\d+(?:[.,]\d+)?)'
    r'|(?P<b>\d+(?:[.,]\d+)?)(?P<post>\s?(?:\$|USD|usd|у\.?е\.?|долл\w*))')
USERNAME_RE = re.compile(r'(?:https?://)?t\.me/\S+|@\w{4,}')
PHONE_RE = re.compile(r'\+?\d[\d\s\-()]{8,}\d')


def add_price(m):
    num = m.group('a') or m.group('b')
    val = float(num.replace(',', '.')) + ADD_USD
    new = str(int(val)) if val.is_integer() else f"{val:.2f}"
    return m.group('pre') + new if m.group('a') else new + m.group('post')


def fix_text(text):
    text = text or ""
    text = USERNAME_RE.sub('', text)
    text = PHONE_RE.sub('', text)
    text = PRICE_RE.sub(add_price, text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return f"{text}\n\n{CONTACT}".strip()


async def main():
    last_id = int(open(STATE).read().strip()) if os.path.exists(STATE) else 0
    async with TelegramClient(StringSession(SESSION), API_ID, API_HASH) as client:
        if last_id == 0:
            # Birinchi ishga tushish: eski postlarni ko'chirmaymiz, faqat joyni belgilaymiz
            latest = await client.get_messages(SOURCE, limit=1)
            last_id = latest[0].id if latest else 0
            print("Boshlang'ich nuqta:", last_id)
        else:
            msgs = [m async for m in client.iter_messages(SOURCE, min_id=last_id, reverse=True)]
            groups = []
            for m in msgs:
                if m.grouped_id and groups and groups[-1][0].grouped_id == m.grouped_id:
                    groups[-1].append(m)
                else:
                    groups.append([m])
            for g in groups:
                caption = fix_text(next((m.text for m in g if m.text), ""))
                media = [m.media for m in g if m.media]
                if media:
                    await client.send_file(TARGET, media if len(media) > 1 else media[0], caption=caption)
                elif caption:
                    await client.send_message(TARGET, caption)
                last_id = g[-1].id
                print("Ko'chirildi:", last_id)
                await asyncio.sleep(2)
    open(STATE, "w").write(str(last_id))

asyncio.run(main())
