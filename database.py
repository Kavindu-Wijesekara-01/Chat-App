from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

# 1. .env ෆයිල් එක ලෝඩ් කරගැනීම
load_dotenv()

# 2. Database URL එක ලබා ගැනීම
DATABASE_URL = os.getenv("DATABASE_URL")

# 3. Database Engine එක පණගැන්වීම
engine = create_async_engine(DATABASE_URL, echo=True)

# 4. Session එකක් (සම්බන්ධතාවයක්) හදාගැනීම
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 5. Database Table හදන්න පාවිච්චි කරන මූලික පන්තිය (Base)
Base = declarative_base()

# 6. Database එකට සම්බන්ධ වෙන්න උදව් කරන ෆන්ක්ෂන් එක
async def get_db():
    async with SessionLocal() as session:
        yield session