import asyncio
import os
import base64
from datetime import datetime
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
import uvicorn
import google.generativeai as genai
import edge_tts

# --- Gemini API の初期設定 ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=AIzaSyCtLih0wPcmjThSyH8dzINNz5tFHyQBApE)
model = genai.GenerativeModel('gemini-2.5-flash')

async def generate_cloud_audio(text: str, voice: str, rate: str, pitch: str) -> bytes:
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except Exception as e:
        print(f"クラウド音声合成エラー: {e}")
        return b""

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("【サーバー側】ブラウザと接続されました。")
    
    chat = model.start_chat(history=[
        {"role": "user", "parts": "あなたは等身大ディスプレイの中にいるサイバーアシスタントです。2〜3文の短めの文章で回答してください。"},
        {"role": "model", "parts": "了解！設定に合わせた最適なボイスでサポートするよ！"}
    ])
    
    current_voice = "ja-JP-NanamiNeural"
    current_rate = "+50%"
    current_pitch = "+30Hz"
    current_mirror = "true"
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # カメラ映像解析機能
            if data.get("type") == "vision_frame":
                image_data = base64.b64decode(data.get("data"))
                response = model.generate_content([
                    "この画像に写っているものを簡潔に説明して。面白いものがあれば一言コメントして。",
                    {"mime_type": "image/jpeg", "data": image_data}
                ])
                reply_text = response.text.strip()
                mp3_data = await generate_cloud_audio(reply_text, current_voice, current_rate, current_pitch)
                if mp3_data:
                    b64_audio = base64.b64encode(mp3_data).decode('utf-8')
                    await websocket.send_json({"type": "audio", "audio": b64_audio, "text": reply_text})
                await websocket.send_json({"type": "end"})
                continue

            if data.get("type") == "settings":
                current_voice = data.get("voice", current_voice)
                current_rate = data.get("rate", current_rate)
                current_pitch = data.get("pitch", current_pitch)
                current_mirror = data.get("mirror", current_mirror)
            elif data.get("type") == "text":
                response = chat.send_message(data.get("text"), stream=True)
                for chunk in response:
                    if chunk.text:
                        mp3_data = await generate_cloud_audio(chunk.text, current_voice, current_rate, current_pitch)
                        if mp3_data:
                            b64_audio = base64.b64encode(mp3_data).decode('utf-8')
                            await websocket.send_json({"type": "audio", "audio": b64_audio, "text": chunk.text})
                await websocket.send_json({"type": "end"})
    except Exception as e:
        print(f"切断: {e}")

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)