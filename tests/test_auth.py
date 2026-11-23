
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete

from main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.session import Session as UserSession


# -------------------------
# 테스트 클라이언트
# -------------------------

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


# -------------------------
# 테스트 계정
# -------------------------

@pytest.fixture
def test_account():
    # 매 실행마다 고유한 계정 ID 생성
    account_id = f"test_{uuid.uuid4().hex[:20]}"
    password = "testpassword123"

    yield {
        "account_id": account_id,
        "password": password,
    }

    # 테스트 종료 후 생성한 데이터 정리
    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(
                User.account_id == account_id
            )
        )

        if user is not None:
            try:
                # FK 제약조건을 고려하여 세션 먼저 삭제
                db.execute(
                    delete(UserSession).where(
                        UserSession.user_id == user.id
                    )
                )

                # 테스트 사용자 삭제
                db.delete(user)
                db.commit()

            except Exception:
                db.rollback()
                raise


# -------------------------
# DB 세션 상태 확인
# -------------------------

def get_user_sessions(user_id: int):
    with SessionLocal() as db:
        return db.scalars(
            select(UserSession)
            .where(UserSession.user_id == user_id)
            .order_by(UserSession.id)
        ).all()


# -------------------------
# Auth API 통합 테스트
# -------------------------

def test_auth_flow(client, test_account):
    account_id = test_account["account_id"]
    password = test_account["password"]

    # 1. 회원가입
    response = client.post(
        "/auth/signup",
        json={
            "account_id": account_id,
            "password": password,
        },
    )

    assert response.status_code == 201, response.text

    signup_data = response.json()
    user_id = signup_data["user_id"]

    assert signup_data["account_id"] == account_id
    assert "created_at" in signup_data

    print("[PASS] 회원가입")

    # 2. 중복 회원가입
    response = client.post(
        "/auth/signup",
        json={
            "account_id": account_id,
            "password": password,
        },
    )

    assert response.status_code == 409

    print("[PASS] 중복 회원가입 차단")

    # 3. 잘못된 비밀번호로 로그인
    response = client.post(
        "/auth/login",
        json={
            "account_id": account_id,
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401

    print("[PASS] 잘못된 비밀번호 차단")

    # 4. 정상 로그인
    response = client.post(
        "/auth/login",
        json={
            "account_id": account_id,
            "password": password,
        },
    )

    assert response.status_code == 200, response.text

    login_data = response.json()

    access_token_1 = login_data["access_token"]
    refresh_token_1 = login_data["refresh_token"]

    assert login_data["user_id"] == user_id
    assert login_data["account_id"] == account_id
    assert login_data["token_type"] == "bearer"

    sessions = get_user_sessions(user_id)

    assert len(sessions) == 1
    assert sessions[0].is_valid is True

    print("[PASS] 로그인 및 세션 생성")

    # 5. 동일 계정 재로그인
    response = client.post(
        "/auth/login",
        json={
            "account_id": account_id,
            "password": password,
        },
    )

    assert response.status_code == 200, response.text

    login_data_2 = response.json()

    access_token_2 = login_data_2["access_token"]
    refresh_token_2 = login_data_2["refresh_token"]

    assert access_token_1 != access_token_2
    assert refresh_token_1 != refresh_token_2

    sessions = get_user_sessions(user_id)

    assert len(sessions) == 2
    assert sessions[0].is_valid is False
    assert sessions[1].is_valid is True

    print("[PASS] 단일 세션 정책")

    # 6. 이전 Refresh Token 사용 차단
    response = client.post(
        "/auth/refresh",
        json={
            "refresh_token": refresh_token_1,
        },
    )

    assert response.status_code == 401

    print("[PASS] 이전 Refresh Token 차단")

    # 7. 정상 Access Token 재발급
    response = client.post(
        "/auth/refresh",
        json={
            "refresh_token": refresh_token_2,
        },
    )

    assert response.status_code == 200, response.text

    refresh_data = response.json()

    assert refresh_data["token_type"] == "bearer"
    assert refresh_data["access_token"] != access_token_2

    sessions = get_user_sessions(user_id)

    assert len(sessions) == 2
    assert sessions[1].is_valid is True

    print("[PASS] Access Token 재발급")

    # 8. 로그아웃
    response = client.post(
        "/auth/logout",
        json={
            "refresh_token": refresh_token_2,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["message"] == "로그아웃되었습니다."

    sessions = get_user_sessions(user_id)

    assert all(not session.is_valid for session in sessions)

    print("[PASS] 로그아웃 및 세션 무효화")

    # 9. 로그아웃한 Refresh Token 재사용
    response = client.post(
        "/auth/refresh",
        json={
            "refresh_token": refresh_token_2,
        },
    )

    assert response.status_code == 401

    print("[PASS] 로그아웃 후 토큰 재발급 차단")

    # 10. 로그아웃한 Access Token으로 회원 탈퇴 시도
    response = client.request(
        "DELETE",
        "/auth/withdraw",
        headers={
            "Authorization": f"Bearer {access_token_2}",
        },
        json={
            "password": password,
        },
    )

    assert response.status_code == 401

    print("[PASS] 로그아웃한 Access Token 차단")

    # 11. 회원 탈퇴를 위한 재로그인
    response = client.post(
        "/auth/login",
        json={
            "account_id": account_id,
            "password": password,
        },
    )

    assert response.status_code == 200, response.text

    login_data_3 = response.json()
    access_token_3 = login_data_3["access_token"]
    refresh_token_3 = login_data_3["refresh_token"]

    print("[PASS] 로그아웃 후 재로그인")

    # 12. 잘못된 비밀번호로 회원 탈퇴
    response = client.request(
        "DELETE",
        "/auth/withdraw",
        headers={
            "Authorization": f"Bearer {access_token_3}",
        },
        json={
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401

    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user is not None
        assert user.is_active is True

    print("[PASS] 잘못된 비밀번호로 회원 탈퇴 차단")

    # 13. 정상 회원 탈퇴
    response = client.request(
        "DELETE",
        "/auth/withdraw",
        headers={
            "Authorization": f"Bearer {access_token_3}",
        },
        json={
            "password": password,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["message"] == "회원 탈퇴가 완료되었습니다."

    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user is not None
        assert user.is_active is False

    sessions = get_user_sessions(user_id)

    assert all(not session.is_valid for session in sessions)

    print("[PASS] 회원 탈퇴 및 계정 비활성화")

    # 14. 탈퇴한 계정으로 로그인
    response = client.post(
        "/auth/login",
        json={
            "account_id": account_id,
            "password": password,
        },
    )

    assert response.status_code == 401

    print("[PASS] 탈퇴한 계정 로그인 차단")

    # 15. 탈퇴한 계정의 Refresh Token 사용
    response = client.post(
        "/auth/refresh",
        json={
            "refresh_token": refresh_token_3,
        },
    )

    assert response.status_code == 401

    print("[PASS] 탈퇴한 계정의 토큰 재사용 차단")
