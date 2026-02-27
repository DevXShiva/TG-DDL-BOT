import os
import uuid
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# --- Config ---
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

# --- Clients Setup ---
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["tg_bot_db"]
links_col = db["links"]

# --- MongoDB TTL Index (Link Expiry 10 Mins) ---
@app.on_event("startup")
async def startup_event():
    await bot.start()
    # Ye line 600 seconds (10 min) baad document delete kar degi
    await links_col.create_index("createdAt", expireAfterSeconds=600)

@bot.on_message(filters.document | filters.video)
async def handle_media(client, message):
    media = message.document or message.video
    file_id = media.file_id
    file_name = media.file_name or "video.mp4"
    unique_id = str(uuid.uuid4())[:10]

    # Save to MongoDB
    await links_col.insert_one({
        "_id": unique_id,
        "file_id": file_id,
        "file_name": file_name,
        "createdAt": datetime.datetime.utcnow()
    })

    host_url = os.getenv("VERCEL_URL", "https://your-app.vercel.app")
    dl_link = f"{host_url}/download/{unique_id}"

    await message.reply_text(
        f"<b>✅ File:</b> {file_name}\n"
        f"<b>⏰ Expiry:</b> 10 Minutes\n\n"
        f"<b>🔗 Download:</b> {dl_link}",
        parse_mode="html"
    )

@app.get("/download/{uid}")
async def stream_file(uid: str):
    # Check MongoDB for file
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

@app.on_event("shutdown")
async def shutdown_event():
    await bot.stop()