import os
import re
import asyncio
import logging
import time
from collections import deque
from threading import Thread
from flask import Flask
from telethon import TelegramClient, events, types
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ======================
#  INITIAL SETUP
# ======================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)

app = Flask(__name__)

# ======================
#  CONFIGURATION LOADER
# ======================
def get_env_variable(name, is_int=True, optional=False):
    """Safely get environment variables with validation"""
    try:
        value = os.environ[name]
        if not value and not optional:
            raise ValueError(f"Empty value for {name}")
        return int(value) if is_int else value
    except KeyError:
        if optional:
            return None
        logging.error(f"❌ Missing required environment variable: {name}")
        raise
    except ValueError as e:
        logging.error(f"❌ Invalid value for {name}: {str(e)}")
        raise

# ======================
#  LOAD CONFIGURATION
# ======================
try:
    # Required credentials
    api_id = get_env_variable('API_ID')
    api_hash = get_env_variable('API_HASH', is_int=False)
    bot_token = get_env_variable('BOT_TOKEN', is_int=False)

    # Support multiple source channels
    source_channels_str = get_env_variable('SOURCE_CHANNELS', is_int=False)
    source_channels = [int(ch.strip()) for ch in source_channels_str.split(',') if ch.strip()]
    if not source_channels:
        raise ValueError("No valid source channels configured")

    # Multiple target channels
    target_channels_str = get_env_variable('TARGET_CHANNELS', is_int=False)
    target_channels = [int(ch.strip()) for ch in target_channels_str.split(',') if ch.strip()]
    if not target_channels:
        raise ValueError("No valid target channels configured")

    # Optional settings with defaults
    queue_delay = int(get_env_variable('QUEUE_DELAY', optional=True) or 120)
    rate_limit = int(get_env_variable('RATE_LIMIT', optional=True) or 60)
    port = int(get_env_variable('PORT', optional=True) or 8080)

except Exception as e:
    logging.critical(f"❌ Configuration error: {str(e)}")
    exit(1)

# ======================
#  FLASK KEEP-ALIVE
# ======================
@app.route('/')
def home():
    return "I'm alive!"

@app.route('/health')
def health():
    return ("Bot is running and connected!", 200) if client.is_connected() else ("Bot is disconnected!", 503)

def run_web():
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run_web, daemon=True).start()

# ======================
#  TELEGRAM BOT SETUP
# ======================
client = TelegramClient('bot_session', api_id, api_hash)
message_queue = deque()
is_forwarding = False
last_forward_time = 0

# ======================
#  MESSAGE PROCESSING
# ======================
def should_forward(message_text, has_media):
    """Check if message meets forwarding criteria"""
    if not message_text or has_media:
        return False

    valid_numbers = ['2000', '2500', '3000', '3100', '4000', '5000', '6666', '10000']
    forbidden_terms = ['http', '@', 'Hazex']

    contains_number = any(num in message_text for num in valid_numbers)
    contains_forbidden = any(term.lower() in message_text.lower() for term in forbidden_terms)

    return contains_number and not contains_forbidden

# ======================
#  MESSAGE HANDLERS
# ======================
@client.on(events.NewMessage(chats=source_channels))
async def handle_new_message(event):
    global is_forwarding, last_forward_time

    try:
        message_text = event.message.message or ""
        logging.info(f"📥 New message: {message_text[:100]}...")

        if should_forward(message_text, event.message.media):
            current_time = time.time()
            if not is_forwarding or (current_time - last_forward_time > rate_limit):
                await forward_message(event)
                last_forward_time = current_time
                is_forwarding = True
                client.loop.create_task(process_queue())
            else:
                message_queue.append(event)
                logging.info(f"🕒 Queued message (queue size: {len(message_queue)})")
        else:
            logging.debug("❌ Message skipped due to filter conditions")

    except Exception as e:
        logging.error(f"🔥 Error in handler: {str(e)}")

async def forward_message(event):
    """Forward message to all target channels with original formatting"""
    try:
        for channel in target_channels:
            try:
                await client.send_message(
                    entity=channel,
                    message=event.message.message,
                    formatting_entities=event.message.entities,
                    link_preview=False
                )
                logging.info(f"✅ Forwarded to {channel}")
                await asyncio.sleep(1)
            except Exception as e:
                logging.error(f"❌ Send failed for {channel}: {str(e)}")
                await asyncio.sleep(3)

        try:
            await event.delete()
            logging.info("🗑️ Source message deleted")
        except Exception as e:
            logging.error(f"❌ Delete failed: {str(e)}")

    except Exception as e:
        logging.error(f"🔥 Forwarding error: {str(e)}")

async def process_queue():
    """Process queued messages with delay"""
    global is_forwarding
    while message_queue:
        await asyncio.sleep(queue_delay)
        event = message_queue.popleft()
        await forward_message(event)
    is_forwarding = False

# ======================
#  CONNECTION MANAGEMENT
# ======================
@client.on(events.Raw)
async def handle_raw(event):
    if isinstance(event, types.UpdateConnectionState):
        if event.state == types.ConnectionState.disconnected:
            logging.warning("⚠️ Bot disconnected! Attempting to reconnect...")
            await asyncio.sleep(5)
            await client.connect()

# ======================
#  MAIN EXECUTION
# ======================
async def run_bot():
    try:
        await client.start(bot_token=bot_token)
        logging.info("🤖 Bot started successfully!")
        await client.run_until_disconnected()
    except Exception as e:
        logging.error(f"❌ Fatal bot error: {str(e)}")
    finally:
        logging.info("🛑 Bot session ended")

if __name__ == "__main__":
    keep_alive()
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped by user")
    except Exception as e:
        logging.error(f"❌ Unexpected error: {str(e)}")

