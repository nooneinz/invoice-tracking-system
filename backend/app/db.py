from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import DATABASE_URL

kw = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {"pool_pre_ping": True}
engine = create_engine(DATABASE_URL, **kw)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
