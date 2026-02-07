from sqlalchemy import Column, Integer, String
from database import Base

# models.py එකේ උඩම මේක තියෙන්න ඕනේ
from sqlalchemy import Column, Integer, String, Boolean # Boolean එකතු කරන්න

# ... (Message class එකට උඩින් මේක දාන්න) ...

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True) # නම Unique වෙන්න ඕනේ
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String) # අපි පාස්වර්ඩ් එක කෙලින්ම සේව් කරන්නේ නෑ
    is_active = Column(Boolean, default=True)
    
class Message(Base):
    __tablename__ = "private_messages" # අලුත් නමක් දුන්නා

    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String)    # යවන කෙනා
    recipient = Column(String) # ලැබෙන කෙනා (මේක තමයි අලුත් කෑල්ල)
    content = Column(String)