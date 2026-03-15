FROM python:3.10-slim

RUN apt-get update && apt-get install -y ffmpeg git gcc g++ libffi-dev libssl-dev python3-dev libc-dev make && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "import pyrogram.errors; setattr(pyrogram.errors, 'GroupcallForbidden', type('GroupcallForbidden', (Exception,), {}))" || true
COPY . .
CMD ["python", "main.py"]
