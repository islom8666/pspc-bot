# Buni FAQAT o'z kompyuteringizda bir marta ishga tushiring:
#   pip install telethon
#   python get_session.py
# Chiqqan uzun matnni GitHub'da SESSION nomli secret qilib saqlang. Hech kimga bermang!
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("API_ID: "))
api_hash = input("API_HASH: ")
with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\nSESSION:\n" + client.session.save())
