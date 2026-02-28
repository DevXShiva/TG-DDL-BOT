import os
import uuid
import datetime
import asyncio
import threading
from flask import Flask, Response, request, jsonify
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient

# --- Configurations ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

app = Flask(__name__)
# in_memory=True taaki Docker/Render pe session file ka error na aaye
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- MongoDB Setup ---
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["tg_bot_db"]
links_col = db["links"]

# --- Helper Function: File Size Readable ---
def get_readable_size(size_in_bytes):
    if size_in_bytes is None: return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024

# --- Bot Handlers ---

# 1. Start Command Handler
@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    welcome_text = (
        f"<b>Hi {message.from_user.mention}! 👋</b>\n\n"
        "Main ek <b>Direct Download Link Generator</b> bot hoon.\n\n"
        "🔹 Mujhe koi bhi File ya Video bhejo.\n"
        "🔹 Main aapko ek High-Speed direct link doonga.\n"
        "🔹 Link <b>10 minute</b> mein expire ho jayega.\n\n"
        "<i>Powered by @YourChannelName</i>"
    )
    await message.reply_text(welcome_text, parse_mode="html")

# 2. Media Handler (Video/Document)
@bot.on_message((filters.document | filters.video) & filters.private)
async def handle_media(client, message):
    media = message.document or message.video
    file_id = media.file_id
    file_name = media.file_name or "video.mp4"
    file_size = get_readable_size(media.file_size)
    unique_id = str(uuid.uuid4())[:10]

    # Save to Mongo with TTL
    await links_col.insert_one({
        "_id": unique_id,
        "file_id": file_id,
        "file_name": file_name,
        "createdAt": datetime.datetime.utcnow() 
    })

    # Render URL logic
    host_url = os.getenv("RENDER_EXTERNAL_URL")
    if not host_url:
        host_url = request.host_url.rstrip('/')
    
    dl_link = f"{host_url}/download/{unique_id}"
    
    response_text = (
        f"<b>✅ File Ready to Download!</b>\n\n"
        f"<b>📄 Name:</b> <code>{file_name}</code>\n"
        f"<b>⚖️ Size:</b> {file_size}\n"
        f"<b>⏰ Expiry:</b> 10 Minutes\n\n"
        f"<b>🔗 Link:</b> <code>{dl_link}</code>\n\n"
        f"<i>Tip: Use IDM for maximum speed! 🚀</i>"
    )
    
    await message.reply_text(response_text, parse_mode="html")

# --- Flask Endpoints ---
@app.route('/')
def home():
    return jsonify({"status": "Online", "mode": "Multi-threaded Streaming"})

@app.route('/download/<uid>')
def download_file(uid):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    data = loop.run_until_complete(links_col.find_one({"_id": uid}))
    
    if not data:
        return "<h1>Error 404: Link Expired or Invalid!</h1><p>Please generate a new link from the bot.</p>", 404

    def generate():
        async def stream():
            async for chunk in bot.stream_media(data['file_id']):
                yield chunk
        
        g = stream()
        while True:
            try:
                chunk = loop.run_until_complete(g.__anext__())
                yield chunk
            except StopAsyncIteration:
                break
            except Exception as e:
                print(f"Streaming Error: {e}")
                break

    return Response(
        generate(),
        mimetype='application/octet-stream',
        headers={"Content-Disposition": f"attachment; filename={data['file_name']}"}
    )

# --- Background Bot Runner ---
async def start_bot_async():
    try:
        await links_col.create_index("createdAt", expireAfterSeconds=600)
        await bot.start()
        print("✅ Bot Started Successfully!")
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_bot_async())
    loop.run_forever()

if __name__ == '__main__':
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
