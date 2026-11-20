# PS.PC — PSN OFFLINE kanalini @psakkaunt bilan sinxronlash (GitHub Actions uchun)
# - yangi postlarni ko'chiradi (narx +40$, kontakt almashtiriladi)
# - manba kanalda o'chirilgan postlarni sizning kanalingizdan ham o'chiradi
import os, re, json, asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION = os.environ["SESSION"]
SOURCE = int(os.environ.get("SOURCE", "-1002567127698"))  # PSN OFFLINE
TARGET = os.environ["TARGET"]                              # @psakkaunt
CONTACT = os.environ.get("CONTACT", "📩 Buyurtma uchun: @PSPC_admin")
ADD_USD = float(os.environ.get("ADD_USD", "40"))
STATE = "last_id.txt"      # ichida JSON saqlanadi: oxirgi id + postlar xaritasi
MAX_PER_RUN = 25           # bir ishga tushishda eng ko'pi bilan shuncha yangi post

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


def load_state():
    try:
        data = json.load(open(STATE))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None  # eski format yoki fayl yo'q


def save_state(state):
    json.dump(state, open(STATE, "w"))


async def purge_target(client):
    ids = [m.id async for m in client.iter_messages(TARGET)]
    for i in range(0, len(ids), 100):
        try:
            await client.delete_messages(TARGET, ids[i:i + 100])
        except Exception as e:
            print("O'chirishda xato:", e)
    print("Kanal tozalandi:", len(ids), "ta xabar")


async def main():
    state = load_state()
    async with TelegramClient(StringSession(SESSION), API_ID, API_HASH) as client:
        if state is None:
            # Yangi tizimga birinchi o'tish: kanalni tozalab, hammasini boshidan ko'chiramiz
            await purge_target(client)
            state = {"last_id": 0, "posts": []}
            save_state(state)

        # 1) Manba kanaldagi hozirgi barcha post id'lari
        all_msgs = [m async for m in client.iter_messages(SOURCE)]
        alive = {m.id for m in all_msgs}

        # 2) Manbada o'chirilganlarini bizda ham o'chiramiz
        keep = []
        for p in state["posts"]:
            if all(s in alive for s in p["src"]):
                keep.append(p)
            else:
                try:
                    await client.delete_messages(TARGET, p["tgt"])
                    print("O'chirildi:", p["src"])
                except Exception as e:
                    print("O'chirishda xato:", e)
        state["posts"] = keep
        save_state(state)

        # 3) Yangi postlarni ko'chiramiz (eskisidan yangisiga)
        new = sorted((m for m in all_msgs if m.id > state["last_id"]), key=lambda m: m.id)
        groups = []
        for m in new:
            if m.action or (not m.text and not m.media):
                continue
            if m.grouped_id and groups and groups[-1][0].grouped_id == m.grouped_id:
                groups[-1].append(m)
            else:
                groups.append([m])

        for g in groups[:MAX_PER_RUN]:
            caption = fix_text(next((m.text for m in g if m.text), ""))
            media = [m.media for m in g if m.media]
            if media:
                sent = await client.send_file(TARGET, media if len(media) > 1 else media[0], caption=caption)
            else:
                sent = await client.send_message(TARGET, caption)
            sent = sent if isinstance(sent, list) else [sent]
            state["posts"].append({"src": [m.id for m in g], "tgt": [s.id for s in sent]})
            state["last_id"] = g[-1].id
            save_state(state)
            print("Ko'chirildi:", g[-1].id)
            await asyncio.sleep(2)

        if len(groups) <= MAX_PER_RUN and new:
            state["last_id"] = max(state["last_id"], new[-1].id)
        save_state(state)
        print("Tayyor. Qolgan yangi postlar:", max(0, len(groups) - MAX_PER_RUN))

asyncio.run(main())
