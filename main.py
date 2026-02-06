import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware  # <--- මේක අලුතෙන් එකතු වුනා
from typing import List
from database import engine, get_db
import models
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

app = FastAPI()

# --- CORS අවසර ලබා දීම (අලුත් කොටස) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ඕනෑම තැනක සිට එන අයට ඉඩ දෙනවා ("*" means allow all)
    allow_credentials=True,
    allow_methods=["*"],  # ඕනෑම ක්‍රමයකට (GET, POST, etc.) ඉඩ දෙනවා
    allow_headers=["*"],
)

# --- Table එක හදන කොටස ---
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

# පරණ මැසේජ් ලබා ගන්නා Route එක
@app.get("/messages")
async def get_messages(db: AsyncSession = Depends(get_db)):
    # 1. Messages table එකෙන් ඔක්කොම තෝරගන්න
    result = await db.execute(select(models.Message))
    # 2. ලිස්ට් එකක් විදියට ගන්න
    messages = result.scalars().all()
    # 3. Frontend එකට යවන්න
    return messages

# --- Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.get("/")
async def get():
    return {"message": "Chat Server with Database is running!"}

# --- 2. WebSocket එක ඇතුලේ Save කරන කෑල්ල ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    db_generator = get_db()
    db = await db_generator.__anext__()
    
    try:
        while True:
            # 1. Frontend එකෙන් එන JSON data එක ගන්නවා
            data = await websocket.receive_text()
            
            # 2. ඒක Python Dictionary එකක් බවට හරවනවා
            message_data = json.loads(data)
            username = message_data['username']
            content = message_data['content']
            
            # 3. Database එකට Save කරනවා (නමත් එක්කම)
            new_message = models.Message(username=username, content=content)
            db.add(new_message)
            await db.commit()
            
            # 4. අනිත් අයට යවනවා (JSON විදියටම)
            response = {
                "username": username,
                "content": content
            }
            await manager.broadcast(json.dumps(response))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(json.dumps({"username": "System", "content": "User left the chat"}))
    finally:
        await db.close()