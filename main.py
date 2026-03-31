import os
import httpx
import tempfile
from fastapi import FastAPI, Request
import google.generativeai as genai

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

app = FastAPI()

async def send_message(chat_id: int, text: str):
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})

async def download_file(file_id: str) -> bytes:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{TELEGRAM_API}/getFile?file_id={file_id}")
        file_path = r.json()["result"]["file_path"]
        r2 = await client.get(f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}")
        return r2.content

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return {"ok": True}

    try:
        if "voice" in message or "audio" in message:
            file_id = message.get("voice", message.get("audio", {})).get("file_id")
            audio_bytes = await download_file(file_id)
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name
            uploaded = genai.upload_file(tmp_path, mime_type="audio/ogg")
            response = model.generate_content([
                "Sei un assistente personale utile e conciso. L'utente ti ha mandato un messaggio vocale. Ascoltalo e rispondi in italiano.",
                uploaded
            ])
            await send_message(chat_id, response.text)
        elif "text" in message:
            response = model.generate_content([
                "Sei un assistente personale utile e conciso. Rispondi in italiano.",
                message["text"]
            ])
            await send_message(chat_id, response.text)
    except Exception as e:
        await send_message(chat_id, f"Errore: {str(e)}")

    return {"ok": True}

@app.get("/")
def root():
    return {"status": "ok"}
