
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# -------------------------
# 회원가입
# -------------------------

class SignupRequest(BaseModel):
    account_id: str = Field(
        min_length=4,
        max_length=30,
        pattern=r"^[a-z0-9_]+$"
    )
    password: str = Field(
        min_length=8,
        max_length=128
    )


class SignupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    account_id: str
    created_at: datetime


# -------------------------
# 로그인
# -------------------------

class LoginRequest(BaseModel):
    account_id: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    account_id: str


# -------------------------
# 로그아웃
# -------------------------

class LogoutRequest(BaseModel):
    refresh_token: str


# -------------------------
# 회원 탈퇴
# -------------------------

class WithdrawRequest(BaseModel):
    password: str


# -------------------------
# 토큰 갱신
# -------------------------

class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# -------------------------
# 공통 응답
# -------------------------

class MessageResponse(BaseModel):
    message: str
