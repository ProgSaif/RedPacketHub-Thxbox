import os
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events
import logging
import asyncio

# ======================
#  CONFIGURATION SETUP
# ======================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Initialize Flask
app = Flask(__name__)

# Load credentials from environment variables
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']
bot_token = os.environ['BOT_TOKEN']
source_channel = int(os.environ['SOURCE_CHANNEL'])
target_channel = int(os.environ['TARGET_CHANNEL'])

# ======================
#  KEEP-ALIVE SERVER
# ======================
def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    Thread(target=run_flask, daemon=True).start()

# ======================
#  TELEGRAM BOT LOGIC
# ======================
client = TelegramClient('bot_session', api_id, api_hash)

@client.on(events.NewMessage(chats=source_channel))
async def handle_new_message(event):
    try:
        msg = event.message
        message_text = msg.text or ""
        
        # Filter conditions
        valid_numbers = ['2000', '3000', '5000', '10000']
        forbidden_content = any([
            'http' in message_text,
            '@' in message_text,
            msg.media is not None
        ])
        
        should_forward = (
            any(num in message_text for num in valid_numbers)
            and not forbidden_content
        )

        if should_forward:
            await client.send_message(
                entity=target_channel,
                message=message_text,
                formatting_entities=msg.entities
            )
            logging.info(f"✅ Forwarded message: {message_text[:50]}...")
            
    except Exception as e:
        logging.error(f"❌ Error: {str(e)}")
        await asyncio.sleep(5)  # Cooldown on errors

# ======================
#  STARTUP & RECOVERY
# ======================
@client.on(events.Disconnected)
async def handle_disconnect():
    logging.warning("⚠️ Bot disconnected! Reconnecting...")
    await asyncio.sleep(5)
    await client.start(bot_token=bot_token)

if __name__ == "__main__":
    keep_alive()
    client.start(bot_token=bot_token)
    logging.info("🤖 Bot started successfully!")
    client.run_until_disconnected()
