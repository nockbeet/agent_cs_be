
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.session import Session as UserSession
from app.core.security import decode_token


# Bearer 인증 스키마
bearer_scheme = HTTPBearer(auto_error=False)


# 인증 실패 예외
def credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보가 유효하지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )


# 현재 로그인된 사용자 조회
def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User:

    # 1. Authorization 헤더 확인
    if credentials is None:
        raise credentials_exception()

    # 2. Access Token 검증
    try:
        payload = decode_token(
            credentials.credentials,
            expected_type="access",
        )
    except ValueError:
        raise credentials_exception()

    user_id = int(payload["sub"])
    session_id = payload["sid"]

    # 3. 세션 조회
    user_session = db.get(
        UserSession,
        session_id,
    )

    if user_session is None:
        raise credentials_exception()

    # 4. 세션 유효성 확인
    if (
        user_session.user_id != user_id
        or not user_session.is_valid
        or user_session.expires_at <= datetime.now(timezone.utc)
    ):
        raise credentials_exception()

    # 5. 사용자 조회
    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise credentials_exception()

    # 6. 인증된 사용자 반환
    return user
