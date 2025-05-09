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

# Handle multiple target channels
target_channels = [int(channel.strip()) for channel in os.environ['TARGET_CHANNELS'].split(',')]

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
        valid_numbers = ['2000', '2500', '3000', '3100', '4000', '5000', '6666', '10000']
        forbidden_content = any([
            'http' in message_text,
            '@' in message_text,
            'Hazex' in message_text,
            msg.media is not None
        ])
        
        should_forward = (
            any(num in message_text for num in valid_numbers)
            and not forbidden_content
        )

        if should_forward:
            for channel in target_channels:
                try:
                    await client.send_message(
                        entity=channel,
                        message=message_text,
                        formatting_entities=msg.entities
                    )
                    logging.info(f"✅ Forwarded to {channel}: {message_text[:50]}...")
                except Exception as channel_error:
                    logging.error(f"❌ Failed to send to {channel}: {str(channel_error)}")
                    await asyncio.sleep(2)  # Delay between attempts
            
    except Exception as e:
        logging.error(f"❌ Main handler error: {str(e)}")
        await asyncio.sleep(5)

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
