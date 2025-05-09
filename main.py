import os
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events, types
import logging
import asyncio

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
#  TELEGRAM BOT
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
            'http' in message_text.lower(),
            '@' in message_text,
            'hazex' in message_text.lower(),
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
                    await asyncio.sleep(1)  # Rate limiting
                except Exception as channel_error:
                    logging.error(f"❌ Failed to send to {channel}: {str(channel_error)}")
                    await asyncio.sleep(3)
            
    except Exception as e:
        logging.error(f"❌ Message processing error: {str(e)}")
        await asyncio.sleep(5)

# ======================
#  CONNECTION HANDLING
# ======================
async def restart_client():
    try:
        if client.is_connected():
            await client.disconnect()
        await client.start(bot_token=bot_token)
        logging.info("✅ Client restarted successfully")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to restart client: {str(e)}")
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
