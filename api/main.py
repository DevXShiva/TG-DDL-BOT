import os
import uuid
import datetime
from flask import Flask, Response, request, jsonify
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import threading

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

# --- Bot Handlers ---
@bot.on_message(filters.document | filters.video)
async def handle_media(client, message):
    media = message.document or message.video
    file_id = media.file_id
    file_name = media.file_name or "video.mp4"
    unique_id = str(uuid.uuid4())[:10]

    # Save to Mongo with TTL (10 min expiry)
    await links_col.insert_one({
        "_id": unique_id,
        "file_id": file_id,
        "file_name": file_name,
        "createdAt": datetime.datetime.utcnow()
    })

    # Render URL logic
    host_url = request.host_url.rstrip('/')
    dl_link = f"{host_url}/download/{unique_id}"
    
    await message.reply_text(
        f"<b>🚀 Fast Download Link:</b>\n\n<code>{dl_link}</code>\n\n"
        f"<b>⏰ Expiry:</b> 10 Minutes\n"
        f"<i>Note: Direct download works with IDM/1DM.</i>",
        parse_mode="html"
    )

# --- Flask Endpoints ---
@app.route('/')
def home():
    return jsonify({"status": "Online", "mode": "Multi-threaded Streaming"})

@app.route('/download/<uid>')
def download_file(uid):
    # Flask ke andar async function ko run karne ka tarika
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    data = loop.run_until_complete(links_col.find_one({"_id": uid}))
    
    if not data:
        return "Link Expired or Invalid!", 404

    def generate():
        # Async generator ko synchronous stream mein convert karna
        async def stream():
            async for chunk in bot.stream_media(data['file_id']):
                yield chunk
        
        # Data chunks ko stream karna
        g = stream()
        while True:
            try:
                chunk = loop.run_until_complete(g.__anext__())
                yield chunk
            except StopAsyncIteration:
                break

    return Response(
        generate(),
        mimetype='application/octet-stream',
        headers={"Content-Disposition": f"attachment; filename={data['file_name']}"}
    )

# --- Background Bot Runner ---
# --- Background Bot Runner ---
def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # MongoDB TTL Index create karein
    loop.run_until_complete(links_col.create_index("createdAt", expireAfterSeconds=600))
    
    # bot.run() ki jagah bot.start() use karein (Signals error fix)
    loop.run_until_complete(bot.start())
    print("✅ Bot Started Successfully!")
    
    # Loop ko chalte rehne dein
    loop.run_forever()

if __name__ == '__main__':
    # Bot ko background thread mein start karein
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    
    # Flask ko main thread mein chalne dein
    port = int(os.environ.get("PORT", 10000)) # Render uses 10000 by default
    app.run(host='0.0.0.0', port=port)
