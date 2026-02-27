# 1. Sabse pehle lightweight Python base image use karenge
FROM python:3.10-slim

# 2. Working directory create karein
WORKDIR /app

# 3. System level dependencies install karein (Tgcrypto aur fast performance ke liye)
# 'build-essential' aur 'libssl-dev' Pyrogram ki speed ke liye zaroori hain
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 4. Sirf requirements pehle copy karein (Docker caching ka fayda lene ke liye)
COPY requirements.txt .

# 5. Dependencies install karein
RUN pip install --no-cache-dir -r requirements.txt

# 6. Ab bacha hua saara project code copy karein
COPY . .

# 7. Port expose karein (Render $PORT dynamic variable use karta hai)
EXPOSE 8080

# 8. Flask + Bot ko run karne ki command
# Buffer ko off rakha hai taaki logs turant dikhein
ENV PYTHONUNBUFFERED=1
CMD ["python", "main.py"]
