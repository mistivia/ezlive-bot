# bot.py
import asyncio
from airc import Client, Message
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

SERVER = "raye.mistivia.com"
PORT = 6697
NICKNAME = "ezlivebot"
CHANNELS = [
    "#xxxxxxxxx",
    "#xxxxxxxxx"
]

TGTOKEN = 'xxxxxxxxx:xxxxxxxx'
TGCHAT = -0000000000000
TGTHREAD = 000

# --- Instantiate the Client ---
irc_client = Client(
    host=SERVER,
    port=PORT,
    nickname=NICKNAME,
    realname="My Awesome Async Bot",
    use_ssl=True
)

tgbot = Bot(token=TGTOKEN)

dp = Dispatcher()

# --- Define Event Handlers using Decorators ---

@irc_client.on('001')  # 001 is the "Welcome to the server" numeric reply
async def on_connect(message: Message):
    """Called once the bot has successfully connected and registered."""
    print("Successfully connected to the IRC server!")
    for channel in CHANNELS:
        print(f"Joining {channel}...")
        await irc_client.join(channel)

@irc_client.on('PRIVMSG')
async def on_message(message: Message):
    """Called on any channel or private message."""
    if not message.prefix:
        return  # Ignore messages without a sender

    sender = message.prefix.nick
    target = message.params[0]  # Channel or our nickname
    text = message.params[1]
    response_target = sender if target == irc_client.nickname else target

    print(f"[{target}] {sender}: {text}")
    if text.startswith('!ping'):
        await irc_client.send_privmsg(response_target, "Pong!")
    msgbody = '<' + sender + '> ' + text
    await tgbot.send_message(chat_id = TGCHAT, message_thread_id = TGTHREAD, text = msgbody)

@dp.message(Command("start"))
async def command_start_handler(message: Message):
    await message.answer("Hello! I'm a bot created with aiogram.")

@dp.message(Command("chatId"))
async def command_start_handler(message: Message):
    res = ''
    res += 'chatid: ' + str(message.chat.id) + '\n'
    if message.message_thread_id is not None:
        res += 'message_thread_id: ' + str(message.message_thread_id) + '\n'
    if message.reply_to_message is not None:
        res += 'reply to msg id: ' + str(message.reply_to_message.message_id)
    await message.answer(res)

def get_sender(msg):
    if msg.from_user is None:
        return
    user = msg.from_user
    if user.username is not None:
        return user.username
    if user.last_name is None:
        return user.first_name + ' ' + user.last_name
    return user.first_name

def get_text(msg):
    if msg.text is None:
        return ''
    return msg.text

@dp.message()
async def msg_handler(msg: Message):
    if msg.chat.id != TGCHAT:
        return
    if msg.message_thread_id is None:
        return
    if msg.message_thread_id != TGTHREAD:
        return
    sender = get_sender(msg)
    if sender is None:
        return
    msgbody = '<' + sender + '> ' + get_text(msg)
    for chan in CHANNELS:
        await irc_client.send_privmsg(chan, msgbody)

async def main():
    await asyncio.gather(irc_client.connect(), dp.start_polling(tgbot))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shutting down.")