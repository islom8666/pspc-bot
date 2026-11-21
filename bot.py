# PS.PC — PSN OFFLINE kanalini @psakkaunt bilan sinxronlash (GitHub Actions uchun)
# - yangi postlarni ko'chiradi (narxga o'yinlar soniga qarab +10/+20/+30/+40$, kontakt almashtiriladi)
# - manba kanalda o'chirilgan postlarni sizning kanalingizdan ham o'chiradi
import os, re, json, asyncio
from telethon import TelegramClient, errors
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION = os.environ["SESSION"]
SOURCE = int(os.environ.get("SOURCE", "-1002567127698"))  # PSN OFFLINE
TARGET = os.environ["TARGET"]                              # @psakkaunt
CONTACT = os.environ.get("CONTACT", "📩 Buyurtma uchun: @PSPC_admin")

# Narx qo'shimchasi o'yinlar soniga qarab:
#   1–2 ta o'yin  -> +10$
#   3–4 ta o'yin  -> +20$
#   5–8 ta o'yin  -> +30$
#   9+ ta o'yin   -> +40$
def extra_usd(games_count):
    if games_count <= 2:
        return 10
    if games_count <= 4:
        return 20
    if games_count <= 8:
        return 30
    return 40
STATE = "last_id.txt"      # ichida JSON saqlanadi: oxirgi id + postlar xaritasi
MAX_PER_RUN = 25           # bir ishga tushishda eng ko'pi bilan shuncha yangi post

PRICE_RE = re.compile(
    r'(?P<pre>\$\s?)(?P<a>\d+(?:[.,]\d+)?)'
    r'|(?P<b>\d+(?:[.,]\d+)?)(?P<post>\s?(?:\$|USD|usd|у\.?е\.?|долл\w*))')
USERNAME_RE = re.compile(r'(?:https?://)?t\.me/\S+|@\w{4,}')
PHONE_RE = re.compile(r'\+?\d[\d\s\-()]{8,}\d')


def add_price(m, add):
    num = m.group('a') or m.group('b')
    val = float(num.replace(',', '.')) + add
    new = str(int(val)) if val.is_integer() else f"{val:.2f}"
    return m.group('pre') + new if m.group('a') else new + m.group('post')


LINE = "_" * 41
SEP_LINE_RE = re.compile(r'^[\s\-–—―━═▬➖_=·•.*~]+$', re.M)
REGION_RE = re.compile(r'^\s*Region\s*:.*$', re.M | re.I)
PAY_RE = re.compile(r'^.*\b(USDT|YANDEX|BTC|XRP|TONCOIN)\b.*$', re.M | re.I)
SELLER_RE = re.compile(r'\s*[/⁄∕／|]\s*[/⁄∕／|].*$', re.M)   # "45$ / / kurbars69" -> "45$"


def cut_price(line):
    # narxdan keyingi hamma narsani kesib tashlaydi: "Price 46$ / / shaznos493" -> "Price 46$"
    m = re.match(r'^(.*?\d+(?:[.,]\d+)?\s?(?:\$|USD|usd))', line) or re.match(r'^(.*?\$\s?\d+(?:[.,]\d+)?)', line)
    return m.group(1) if m else line


def fix_text(text):
    text = text or ""
    text = REGION_RE.sub(lambda m: ' '.join(re.findall(r'only\s*ps\s*[45]', m.group(0), re.I)), text)
    text = PAY_RE.sub('', text)
    text = SELLER_RE.sub('', text)
    text = SEP_LINE_RE.sub('', text)
    text = USERNAME_RE.sub('', text)
    text = PHONE_RE.sub('', text)

    # Avval o'yinlarni sanaymiz (narx va "Only PS5" qatorlaridan tashqari hamma qator = o'yin)
    raw = [l.strip() for l in text.splitlines() if l.strip()]
    n_games = sum(1 for l in raw
                  if not re.search(r'price|narx|цена', l, re.I)
                  and not re.fullmatch(r'only\s*ps\s*[45]', l, re.I))
    add = extra_usd(n_games)
    print(f"O'yinlar soni: {n_games} -> +{add}$")

    text = PRICE_RE.sub(lambda m: add_price(m, add), text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    price = [cut_price(l) for l in lines if re.search(r'price|narx|цена', l, re.I)]
    only = [l for l in lines if re.fullmatch(r'only\s*ps\s*[45]', l, re.I)]
    games = [l for l in lines if not re.search(r'price|narx|цена', l, re.I) and l not in only]
    out = ""
    if games:
        out += f"{LINE}\n\n" + "\n".join(games) + f"\n{LINE}\n"
    if only:
        out += "\n".join(o.title().replace("Ps", "PS") for o in only) + "\n"
    elif games:
        out += "\n"
    if price:
        out += "\n".join(price) + "\n"
    return f"{out}\n{CONTACT}".strip()


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
        client.parse_mode = None   # matn aynan shunday yuborilsin (___ chiziqlar buzilmasin)
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
            if m.action or (not m.raw_text and not m.media):
                continue
            if m.grouped_id and groups and groups[-1][0].grouped_id == m.grouped_id:
                groups[-1].append(m)
            else:
                groups.append([m])

        for g in groups[:MAX_PER_RUN]:
            caption = fix_text(next((m.raw_text for m in g if m.raw_text), ""))
            media = [m.media for m in g if m.media]
            if media:
                try:
                    sent = await client.send_file(TARGET, media if len(media) > 1 else media[0], caption=caption)
                    sent = sent if isinstance(sent, list) else [sent]
                except errors.MediaCaptionTooLongError:
                    # Matn juda uzun (1024 belgidan ko'p): rasmni alohida, matnni alohida yuboramiz
                    pics = await client.send_file(TARGET, media if len(media) > 1 else media[0])
                    pics = pics if isinstance(pics, list) else [pics]
                    txt = await client.send_message(TARGET, caption[:4096])
                    sent = pics + [txt]
            else:
                sent = [await client.send_message(TARGET, caption[:4096])]
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
