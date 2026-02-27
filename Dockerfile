FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Saara code copy karein (isme api/ folder bhi copy ho jayega)
COPY . .

EXPOSE 8080

ENV PYTHONUNBUFFERED=1

# --- YAHAN HAI FIX ---
# Humne 'main.py' ko 'api/main.py' se replace kar diya hai
CMD ["python", "api/main.py"]
