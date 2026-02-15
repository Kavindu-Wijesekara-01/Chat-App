from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

# 1. අලුත් Channel Table එක
class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

# 2. මැසේජ් එකට 'channel_name' එකතු කිරීම
class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String)
    
    # මැසේජ් එක යන්නේ Channel එකකටද? (උදා: 'Python')
    # නැත්නම් කෙලින්ම යාලුවෙක්ටද? (උදා: 'Kamal')
    channel_name = Column(String, nullable=True) 
    recipient = Column(String, nullable=True)
    
    content = Column(String)