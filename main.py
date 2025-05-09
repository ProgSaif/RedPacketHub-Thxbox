import os
import re
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events, types
import logging
import asyncio
from datetime import datetime

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
#  ENVIRONMENT VARIABLES
# ======================
def get_env_variable(name, is_int=True):
    try:
        value = os.environ[name]
        return int(value) if is_int else value
    except KeyError:
        logging.error(f"❌ Missing required environment variable: {name}")
        raise
    except ValueError:
        logging.error(f"❌ Invalid value for {name}. Must be {'integer' if is_int else 'string'}")
        raise

try:
    api_id = get_env_variable('API_ID')
    api_hash = get_env_variable('API_HASH', False)
    bot_token = get_env_variable('BOT_TOKEN', False)
    source_channel = get_env_variable('SOURCE_CHANNEL')
    
    # Handle multiple target channels
    target_channels_str = os.environ.get('TARGET_CHANNELS', '')
    if not target_channels_str:
        raise ValueError("TARGET_CHANNELS environment variable is empty")
    
    target_channels = [int(ch.strip()) for ch in target_channels_str.split(',')]
    if not target_channels:
        raise ValueError("No valid target channels configured")

    # Optional delay between forwards (in seconds)
    forward_delay = int(os.environ.get('FORWARD_DELAY', 1))

except Exception as e:
    logging.error(f"❌ Configuration error: {str(e)}")
    exit(1)

# ======================
#  FLASK KEEP-ALIVE
# ======================
def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    Thread(target=run_flask, daemon=True).start()

# ======================
#  MESSAGE PROCESSING
# ======================
def clean_message(text):
    """Clean and normalize message text"""
    if not text:
        return ""
    
    # Remove special formatting characters
    text = re.sub(r'[\u202e\u202d\u200e\u200f]', '', text)  # RTL/LTR marks
    
    # Normalize whitespace and line breaks
    text = '\n'.join(
        ' '.join(line.split())
        for line in text.split('\n')
        if line.strip()
    )
    
    return text.strip()

def should_forward_message(text):
    """Determine if message should be forwarded"""
    if not text:
        return False
    
    # Required keywords/numbers
    valid_terms = ['2000', '2500', '3000', '3100', '4000', '5000', '6666', '10000']
    
    # Forbidden content patterns
    forbidden_patterns = [
        r'http[s]?://',  # URLs
        r'@\w+',         # Mentions
        r'hazex',        # Forbidden word
        r'[\U0001F600-\U0001F64F]'  # Emojis (optional)
    ]
    
    # Check for required terms
    has_valid_terms = any(term in text for term in valid_terms)
    
    # Check for forbidden content
    has_forbidden = any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in forbidden_patterns
    )
    
    return has_valid_terms and not has_forbidden

# ======================
#  TELEGRAM BOT
# ======================
client = TelegramClient('bot_session', api_id, api_hash)

@client.on(events.NewMessage(chats=source_channel))
async def handle_new_message(event):
    try:
        msg = event.message
        message_text = clean_message(msg.text)
        
        # Skip if message has media (photos, videos, etc.)
        if msg.media:
            logging.info("⏩ Skipping media message")
            return
            
        # Check forwarding conditions
        if should_forward_message(message_text):
            for channel in target_channels:
                try:
                    # Add timestamp to forwarded message
                    timestamp = datetime.now().strftime('[%H:%M]')
                    formatted_msg = f"{timestamp}\n{message_text}"
                    
                    await client.send_message(
                        entity=channel,
                        message=formatted_msg,
                        formatting_entities=msg.entities,
                        link_preview=False
                    )
                    logging.info(f"✅ Forwarded to {channel}: {formatted_msg[:100]}...")
                    await asyncio.sleep(forward_delay)  # Respect rate limits
                    
                except Exception as channel_error:
                    logging.error(f"❌ Failed to send to {channel}: {str(channel_error)}")
                    await asyncio.sleep(3)  # Wait longer after errors
            
    except Exception as e:
        logging.error(f"❌ Message processing error: {str(e)}")
        await asyncio.sleep(5)

# ======================
#  CONNECTION MANAGEMENT
# ======================
async def restart_client():
    retries = 0
    max_retries = 5
    while retries < max_retries:
        try:
            if client.is_connected():
                await client.disconnect()
            await client.start(bot_token=bot_token)
            logging.info("✅ Client restarted successfully")
            return True
        except Exception as e:
            retries += 1
            wait_time = min(2 ** retries, 30)  # Exponential backoff
            logging.error(f"❌ Failed to restart client (attempt {retries}/{max_retries}): {str(e)}")
            await asyncio.sleep(wait_time)
    return False

@client.on(events.Raw)
async def handle_raw(event):
    if isinstance(event, types.UpdateConnectionState):
        if event.state == types.ConnectionState.disconnected:
            logging.warning("⚠️ Bot disconnected! Attempting to reconnect...")
            await asyncio.sleep(5)
            await restart_client()

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
