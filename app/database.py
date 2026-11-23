
import os

from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session


# .env 환경변수 불러오기
load_dotenv()


# PostgreSQL 연결 정보
DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME"),
)


# SQLAlchemy Engine 생성
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


# DB 세션 생성
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


# ORM 모델의 공통 Base
class Base(DeclarativeBase):
    pass


# FastAPI 의존성 주입용 DB 세션
def get_db():
    db: Session = SessionLocal()

    try:
        yield db
    finally:
        db.close()
