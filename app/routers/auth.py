
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.session import Session as UserSession

from app.schemas.auth import (
    SignupRequest,
    SignupResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    LogoutRequest,
    WithdrawRequest,
    MessageResponse,
)

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

from app.core.dependencies import (
    get_current_user,
    credentials_exception,
)


router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


# -------------------------
# 회원가입
# -------------------------

@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    request: SignupRequest,
    db: Annotated[Session, Depends(get_db)],
):
    # 1. account_id 중복 확인
    existing_user = db.scalar(
        select(User).where(
            User.account_id == request.account_id
        )
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 계정 ID입니다.",
        )

    # 2. 비밀번호 해싱
    try:
        password_hash = hash_password(request.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 3. User ORM 객체 생성
    new_user = User(
        account_id=request.account_id,
        password_hash=password_hash,
    )

    db.add(new_user)

    try:
        db.commit()
        db.refresh(new_user)

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 계정 ID입니다.",
        ) from exc

    return SignupResponse(
        user_id=new_user.id,
        account_id=new_user.account_id,
        created_at=new_user.created_at,
    )


# -------------------------
# 로그인
# -------------------------


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    request: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        # 1. 사용자 조회 및 행 잠금
        user = db.scalar(
            select(User)
            .where(User.account_id == request.account_id)
            .with_for_update()
        )

        # 2. 계정 및 비밀번호 확인
        if (
            user is None
            or not user.is_active
            or not verify_password(
                request.password,
                user.password_hash,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="계정 ID 또는 비밀번호가 올바르지 않습니다.",
            )

        # 3. 기존 유효 세션 무효화
        db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user.id,
                UserSession.is_valid.is_(True),
            )
            .values(is_valid=False)
        )

        # 4. Refresh Token 생성
        refresh_token = create_refresh_token(user.id)
        refresh_token_hash = hash_refresh_token(refresh_token)

        # 5. 새 세션 생성
        now = datetime.now(timezone.utc)

        new_session = UserSession(
            user_id=user.id,
            refresh_token_hash=refresh_token_hash,
            expires_at=now + timedelta(
                days=REFRESH_TOKEN_EXPIRE_DAYS
            ),
        )

        db.add(new_session)
        db.flush()

        # 6. Access Token 생성
        access_token = create_access_token(
            user_id=user.id,
            session_id=new_session.id,
        )

        # 7. 변경 사항 저장
        db.commit()

    except Exception:
        db.rollback()
        raise

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        account_id=user.account_id,
    )



# -------------------------
# 토큰 재발급
# -------------------------

@router.post(
    "/refresh",
    response_model=RefreshResponse,
)
def refresh(
    request: RefreshRequest,
    db: Annotated[Session, Depends(get_db)],
):
    # 1. Refresh Token 검증
    try:
        payload = decode_token(
            request.refresh_token,
            expected_type="refresh",
        )
    except ValueError:
        raise credentials_exception()

    user_id = int(payload["sub"])

    # 2. Refresh Token 해시로 세션 조회
    token_hash = hash_refresh_token(
        request.refresh_token
    )

    user_session = db.scalar(
        select(UserSession).where(
            UserSession.refresh_token_hash == token_hash
        )
    )

    if user_session is None:
        raise credentials_exception()

    # 3. 세션 유효성 확인
    if (
        user_session.user_id != user_id
        or not user_session.is_valid
        or user_session.expires_at <= datetime.now(timezone.utc)
    ):
        raise credentials_exception()

    # 4. 사용자 활성 상태 확인
    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise credentials_exception()

    # 5. 새 Access Token 발급
    access_token = create_access_token(
        user_id=user.id,
        session_id=user_session.id,
    )

    return RefreshResponse(
        access_token=access_token,
    )


# -------------------------
# 로그아웃
# -------------------------

@router.post(
    "/logout",
    response_model=MessageResponse,
)
def logout(
    request: LogoutRequest,
    db: Annotated[Session, Depends(get_db)],
):
    # 1. Refresh Token 검증
    try:
        payload = decode_token(
            request.refresh_token,
            expected_type="refresh",
        )
    except ValueError:
        raise credentials_exception()

    user_id = int(payload["sub"])

    # 2. 세션 조회
    token_hash = hash_refresh_token(
        request.refresh_token
    )

    user_session = db.scalar(
        select(UserSession).where(
            UserSession.refresh_token_hash == token_hash
        )
    )

    if (
        user_session is None
        or user_session.user_id != user_id
        or not user_session.is_valid
        or user_session.expires_at <= datetime.now(timezone.utc)
    ):
        raise credentials_exception()

    # 3. 세션 무효화
    user_session.is_valid = False

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return MessageResponse(
        message="로그아웃되었습니다."
    )


# -------------------------
# 회원 탈퇴
# -------------------------


@router.delete(
    "/withdraw",
    response_model=MessageResponse,
)
def withdraw(
    request: WithdrawRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
):
    try:
        # 1. 사용자 행 잠금
        user = db.scalar(
            select(User)
            .where(User.id == current_user.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        # 2. 계정 활성 상태 재확인
        if user is None or not user.is_active:
            raise credentials_exception()

        # 3. 비밀번호 재확인
        if not verify_password(
            request.password,
            user.password_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="비밀번호가 올바르지 않습니다.",
            )

        # 4. 계정 비활성화
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc)

        # 5. 모든 세션 무효화
        db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user.id,
                UserSession.is_valid.is_(True),
            )
            .values(is_valid=False)
        )

        # 6. 변경 사항 저장
        db.commit()

    except Exception:
        db.rollback()
        raise

    return MessageResponse(
        message="회원 탈퇴가 완료되었습니다."
    )
