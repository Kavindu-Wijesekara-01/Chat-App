from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from typing import Dict, List
import json
import hashlib

from database import engine, get_db
import models
import schemas

# --- Auth Helper Functions ---
def get_password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password, hashed_password):
    return get_password_hash(plain_password) == hashed_password

app = FastAPI()

# --- CORS Setup (Frontend එකට Backend එකත් එක්ක කතා කරන්න දෙන අවසරය) ---
origins = [
    "http://localhost",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
    "http://127.0.0.1:8000",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Server Start වෙනකොට Database Reset කිරීම (Fix for 'sender' error) ---
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # ⚠️ අවධානයට: මේ පේළියෙන් පරණ Tables ඔක්කොම මකලා දානවා (Reset)
        # මේක නිසා අර 'sender column missing' ප්‍රශ්නය විසඳෙනවා.
        await conn.run_sync(models.Base.metadata.drop_all)
        
        # දැන් අලුත්, නිවැරදි Tables ආයේ හදනවා
        await conn.run_sync(models.Base.metadata.create_all)
    
    # Default Rooms ටික හදනවා
    default_channels = ["General", "Python-Help", "Java-Help", "Web-Dev", "DevOps", "Career-Advice"]
    
    async for db in get_db():
        for channel_name in default_channels:
            result = await db.execute(select(models.Channel).where(models.Channel.name == channel_name))
            if not result.scalars().first():
                db.add(models.Channel(name=channel_name))
        await db.commit()
        break

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections[username] = websocket

    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]

    async def send_private(self, message: str, recipient: str):
        if recipient in self.active_connections:
            await self.active_connections[recipient].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

manager = ConnectionManager()

# --- API Endpoints ---

@app.post("/register")
async def register(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).where(models.User.username == user.username))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username taken")
    
    new_user = models.User(
        username=user.username, 
        email=user.email, 
        hashed_password=get_password_hash(user.password)
    )
    db.add(new_user)
    await db.commit()
    return {"message": "User created"}

@app.post("/login")
async def login(user: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).where(models.User.username == user.username))
    db_user = result.scalars().first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return {"username": db_user.username}

@app.get("/channels")
async def get_channels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Channel))
    return result.scalars().all()

@app.get("/users/{current_user}")
async def get_users(current_user: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).where(models.User.username != current_user))
    return result.scalars().all()

@app.get("/messages/channel/{channel_name}")
async def get_channel_msgs(channel_name: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Message).where(models.Message.channel_name == channel_name))
    return result.scalars().all()

@app.get("/messages/private/{user1}/{user2}")
async def get_private_msgs(user1: str, user2: str, db: AsyncSession = Depends(get_db)):
    query = select(models.Message).where(
        or_(
            (models.Message.sender == user1) & (models.Message.recipient == user2),
            (models.Message.sender == user2) & (models.Message.recipient == user1)
        )
    ).order_by(models.Message.id)
    result = await db.execute(query)
    return result.scalars().all()

# --- WebSocket Endpoint ---
@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await manager.connect(websocket, username)
    db_generator = get_db()
    db = await db_generator.__anext__()
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"RECEIVED DATA from {username}: {data}") # Debug Log

            msg_data = json.loads(data)
            msg_type = msg_data.get('type')
            target = msg_data.get('target')
            content = msg_data.get('content')
            
            if msg_type == 'channel':
                print(f"Saving Channel Message to {target}...")
                new_msg = models.Message(sender=username, channel_name=target, content=content)
                db.add(new_msg)
                await db.commit()
                
                await manager.broadcast(json.dumps({
                    "type": "channel", "channel": target, 
                    "sender": username, "content": content
                }))

            elif msg_type == 'private':
                print(f"Saving Private Message to {target}...")
                new_msg = models.Message(sender=username, recipient=target, content=content)
                db.add(new_msg)
                await db.commit()
                
                resp = json.dumps({
                    "type": "private", "sender": username, 
                    "recipient": target, "content": content
                })
                await manager.send_private(resp, target)
                await manager.send_private(resp, username)

    except WebSocketDisconnect:
        manager.disconnect(username)
        print(f"User {username} disconnected")
    except Exception as e:
        print(f"ERROR Occurred: {e}")
    finally:
        await db.close()