
# app/core/security.py

import hashlib
import os
import uuid

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from dotenv import load_dotenv
from jwt import ExpiredSignatureError, InvalidTokenError


# -------------------------
# 환경변수 설정
# -------------------------

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)

REFRESH_TOKEN_EXPIRE_DAYS = int(
    os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
)

if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY 환경변수가 설정되지 않았습니다."
    )

if ALGORITHM != "HS256":
    raise RuntimeError(
        "지원하지 않는 JWT 알고리즘입니다."
    )


# -------------------------
# 비밀번호 해싱
# -------------------------

def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError(
            "비밀번호는 UTF-8 기준 72바이트를 초과할 수 없습니다."
        )

    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    )

    return hashed.decode("utf-8")


# -------------------------
# 비밀번호 검증
# -------------------------

def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    password_bytes = plain_password.encode("utf-8")

    if len(password_bytes) > 72:
        return False

    try:
        return bcrypt.checkpw(
            password_bytes,
            hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


# -------------------------
# Access Token 생성
# -------------------------

def create_access_token(user_id: int, session_id: int) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "sid": session_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        ),
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


# -------------------------
# Refresh Token 생성
# -------------------------

def create_refresh_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(
            days=REFRESH_TOKEN_EXPIRE_DAYS
        ),
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


# -------------------------
# JWT 검증
# -------------------------


def decode_token(
    token: str,
    expected_type: str
) -> dict:
    if expected_type not in ("access", "refresh"):
        raise ValueError(
            "expected_type은 access 또는 refresh여야 합니다."
        )

    # 토큰 유형에 따른 필수 클레임
    required_claims = [
        "sub", "type", "iat", "exp", "jti"
    ]

    if expected_type == "access":
        required_claims.append("sid")

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={
                "require": required_claims
            }
        )

    except ExpiredSignatureError as exc:
        raise ValueError(
            "토큰이 만료되었습니다."
        ) from exc

    except InvalidTokenError as exc:
        raise ValueError(
            "유효하지 않은 토큰입니다."
        ) from exc

    # 토큰 유형 확인
    if payload.get("type") != expected_type:
        raise ValueError(
            "토큰 유형이 올바르지 않습니다."
        )

    # 사용자 ID 검증
    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "토큰의 사용자 ID가 올바르지 않습니다."
        ) from exc

    if user_id <= 0:
        raise ValueError(
            "토큰의 사용자 ID가 올바르지 않습니다."
        )

    # Access Token의 세션 ID 검증
    if expected_type == "access":
        session_id = payload.get("sid")

        if (
            type(session_id) is not int
            or session_id <= 0
        ):
            raise ValueError(
                "토큰의 세션 ID가 올바르지 않습니다."
            )

    return payload


# -------------------------
# Refresh Token 해싱
# -------------------------

def hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(
        refresh_token.encode("utf-8")
    ).hexdigest()
