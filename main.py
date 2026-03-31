import os
import httpx
import tempfile
from fastapi import FastAPI, Request
from google import genai
from google.genai import types

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

client = genai.Client(api_key=GEMINI_API_KEY)

app = FastAPI()

async def send_message(chat_id: int, text: str):
    async with httpx.AsyncClient() as http:
        await http.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})

async def download_file(file_id: str) -> bytes:
    async with httpx.AsyncClient() as http:
        r = await http.get(f"{TELEGRAM_API}/getFile?file_id={file_id}")
        file_path = r.json()["result"]["file_path"]
        r2 = await http.get(f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}")
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
            with open(tmp_path, "rb") as af:
                audio_data = af.read()
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Part.from_bytes(data=audio_data, mime_type="audio/ogg"),
                    "Sei un assistente personale utile e conciso. Ascolta il messaggio vocale e rispondi in italiano."
                ]
            )
            await send_message(chat_id, response.text)
        elif "text" in message:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"Sei un assistente personale utile e conciso. Rispondi in italiano. Messaggio: {message['text']}"
            )
            await send_message(chat_id, response.text)
    except Exception as e:
        await send_message(chat_id, f"Errore: {str(e)}")

    return {"ok": True}

@app.get("/")
def root():
    return {"status": "ok"}
