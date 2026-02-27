import os
import uuid
import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

# Config
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL") # Render khud deta hai ye

app = FastAPI()
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# MongoDB Setup
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["tg_bot_db"]
links_col = db["links"]

@app.on_event("startup")
async def startup_event():
    # TTL Index: Link 10 min mein expire hoga
    await links_col.create_index("createdAt", expireAfterSeconds=600)
    asyncio.create_task(bot.start()) # Bot starts in background

@app.get("/")
def home():
    return {"status": "Server is Live", "bot": "Active"}

@bot.on_message(filters.document | filters.video)
async def handle_media(client, message):
    media = message.document or message.video
    file_id = media.file_id
    file_name = media.file_name or "video.mp4"
    unique_id = str(uuid.uuid4())[:10]

    await links_col.insert_one({
        "_id": unique_id,
        "file_id": file_id,
        "file_name": file_name,
        "createdAt": datetime.datetime.utcnow()
    })

    # Render ka URL automatic use hoga
    dl_link = f"{RENDER_EXTERNAL_URL}/download/{unique_id}"
    
    await message.reply_text(
        f"<b>✅ File Name:</b> {file_name}\n"
        f"<b>⏰ Expiry:</b> 10 Minutes\n\n"
        f"<b>🚀 Direct Download:</b> {dl_link}",
        parse_mode="html"
    )

@app.get("/download/{uid}")
async def stream_file(uid: str):
    data = await links_col.find_one({"_id": uid})
    if not data:
        raise HTTPException(status_code=404, detail="Link expired or invalid")

    async def file_generator():
        async for chunk in bot.stream_media(data["file_id"]):
            yield chunk

    return StreamingResponse(
        file_generator(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={data['file_name']}"}
    )
