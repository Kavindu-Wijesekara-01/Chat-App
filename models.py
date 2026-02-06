from sqlalchemy import Column, Integer, String
from database import Base

class Message(Base):
    # අපි නම පොඩ්ඩක් වෙනස් කළා අලුත් Table එකක් හැදෙන්න
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)  # <--- මේක තමයි අලුතෙන් එකතු වුනේ
    content = Column(String)