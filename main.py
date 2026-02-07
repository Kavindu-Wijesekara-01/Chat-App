from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from typing import Dict
import json
import hashlib

from database import engine, get_db
import models
import schemas

# --- auth.py එකෙන් hash function එක ගන්න (සරලව) ---
def get_password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password, hashed_password):
    return get_password_hash(plain_password) == hashed_password

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

# --- Connection Manager (1-on-1 Chat සඳහා වෙනස් කළා) ---
class ConnectionManager:
    def __init__(self):
        # List එකක් වෙනුවට Dictionary එකක් පාවිච්චි කරනවා
        # Key = Username, Value = WebSocket Connection
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections[username] = websocket

    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]

    # අදාල කෙනාට විතරක් යවන ෆන්ක්ෂන් එක
    async def send_personal_message(self, message: str, recipient: str):
        if recipient in self.active_connections:
            await self.active_connections[recipient].send_text(message)

manager = ConnectionManager()

# --- Routes ---

@app.post("/register")
async def register(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).where(models.User.username == user.username))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username taken")
    
    new_user = models.User(username=user.username, email=user.email, hashed_password=get_password_hash(user.password))
    db.add(new_user)
    await db.commit()
    return {"message": "User created"}

@app.post("/login")
async def login(user: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).where(models.User.username == user.username))
    db_user = result.scalars().first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return {"username": db_user.username} # සරලව නම යවනවා

# 1. අනිත් Users ලාගේ ලිස්ට් එක ගන්න API එක
@app.get("/users/{current_username}")
async def get_users(current_username: str, db: AsyncSession = Depends(get_db)):
    # තමන් හැර අනිත් සියලුම අයව තෝරගන්නවා
    result = await db.execute(select(models.User.username).where(models.User.username != current_username))
    users = result.scalars().all()
    return users

# 2. මට අදාල මැසේජ් විතරක් ගන්න API එක
@app.get("/messages/{username}/{other_user}")
async def get_private_messages(username: str, other_user: str, db: AsyncSession = Depends(get_db)):
    # මම යැවූ හෝ මට එවූ මැසේජ් විතරක් ගන්නවා
    query = select(models.Message).where(
        or_(
            (models.Message.sender == username) & (models.Message.recipient == other_user),
            (models.Message.sender == other_user) & (models.Message.recipient == username)
        )
    ).order_by(models.Message.id)
    
    result = await db.execute(query)
    return result.scalars().all()

# 3. WebSocket (Username එකත් එක්ක Connect වෙන්න ඕනේ)
@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(websocket, username)
    db_generator = get_db()
    db = await db_generator.__anext__()
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            recipient = message_data['recipient']
            content = message_data['content']
            
            # Database එකට Save කරනවා
            new_msg = models.Message(sender=username, recipient=recipient, content=content)
            db.add(new_msg)
            await db.commit()
            
            # 1. Recipient ට යවනවා (එයා Online නම්)
            response = json.dumps({"sender": username, "content": content})
            await manager.send_personal_message(response, recipient)
            
            # 2. Sender (මටම) පෙන්වන්න ආපහු එවනවා
            await manager.send_personal_message(response, username)
            
    except WebSocketDisconnect:
        manager.disconnect(username)
    finally:
        await db.close()