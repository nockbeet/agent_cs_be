import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.user import router as user_router
from app.routers.post import router as post_router
from app.routers.comment import router as comment_router

load_dotenv()

# FastAPI 애플리케이션 생성
app = FastAPI(
    title="Agent-CS API",
    description="컴퓨터공학과 학생 커뮤니티 서비스 API",
    version="1.0.0",
)

# CORS 설정
frontend_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "FRONTEND_URL",
        "http://localhost:3000,http://localhost:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(post_router)
app.include_router(comment_router)