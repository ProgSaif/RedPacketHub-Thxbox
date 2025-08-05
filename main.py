import os
import re
import asyncio
from telethon.sync import TelegramClient, events
from telethon.sessions import StringSession
from telegram import Bot
from telegram.error import TelegramError

# Configuration from environment variables
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('BOT_TOKEN')
session_string = os.getenv('SESSION_STRING')
source_chat_id = int(os.getenv('SOURCE_CHAT_ID'))
destination_channel_id = int(os.getenv('DESTINATION_CHANNEL_ID'))

# Initialize both clients
user_client = TelegramClient(StringSession(session_string), api_id, api_hash)
bot_client = Bot(token=bot_token)

async def format_message(text):
    crypto_match = re.match(r'^([A-Z]+)', text)
    crypto_name = crypto_match.group(1) if crypto_match else "CRYPTO"
    
    amount_match = re.search(r'(\d+ \| ~[\d.]+ [A-Z]+)', text)
    usdt_match = re.search(r'(~[\d.]+ USDT)', text)
    answer_match = re.search(r'Answer:\s*(.*?)(?=\n#|$)', text, re.DOTALL)
    
    answer = answer_match.group(1).strip() if answer_match else ""
    answer = re.sub(r'copy\s*[^\w\s]*', '', answer)
    answer = re.sub(r'([!]+)', '❕', answer).strip()
    
    formatted_msg = f"❤️‍🩹 {crypto_name} ❤️‍🩹\n"
    formatted_msg += f"💎 {amount_match.group(1) if amount_match else ''}\n"
    formatted_msg += f"💰 {usdt_match.group(1) if usdt_match else ''}\n\n"
    formatted_msg += f"Answer:\n{answer}❕{answer}❕\n\n"
    formatted_msg += "#square #slot"
    
    return formatted_msg

@user_client.on(events.NewMessage(chats=source_chat_id))
async def handle_new_message(event):
    try:
        if not event.message.media:
            formatted_message = await format_message(event.message.text)
            
            # Try sending via bot first, fallback to user account
            try:
                await bot_client.send_message(
                    chat_id=destination_channel_id,
                    text=formatted_message
                )
            except TelegramError as e:
                print(f"Bot failed to send message, falling back to user account: {e}")
                await user_client.send_message(
                    destination_channel_id,
                    formatted_message
                )
                
    except Exception as e:
        print(f"Error processing message: {e}")

async def main():
    # Start the user client
    await user_client.start()
    
    # Verify bot connection
    try:
        bot_info = await bot_client.get_me()
        print(f"Bot connected as @{bot_info.username}")
    except TelegramError as e:
        print(f"Bot connection failed: {e}")
    
    print("Forwarder bot is running...")
    await user_client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
