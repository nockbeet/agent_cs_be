
from fastapi import FastAPI

from app.routers.auth import router as auth_router
from app.routers.user import router as user_router
from app.routers.post import router as post_router
from app.routers.comment import router as comment_router

# FastAPI 애플리케이션 생성
app = FastAPI(
    title="Agent-CS API",
    description="컴퓨터공학과 학생 커뮤니티 서비스 API",
    version="1.0.0",
)


# 라우터 등록
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(post_router)
app.include_router(comment_router)