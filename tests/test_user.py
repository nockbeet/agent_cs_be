
import importlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

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
# 테스트 계정 생성 및 정리
# -------------------------

@pytest.fixture
def account_factory(client):
    created_account_ids = []

    def create_account():
        account_id = f"test_{uuid.uuid4().hex[:20]}"
        password = "testpassword123"

        # 회원가입 요청 전부터 정리 대상으로 등록
        created_account_ids.append(account_id)

        response = client.post(
            "/auth/signup",
            json={
                "account_id": account_id,
                "password": password,
            },
        )

        assert response.status_code == 201, response.text

        user_id = response.json()["user_id"]

        response = client.post(
            "/auth/login",
            json={
                "account_id": account_id,
                "password": password,
            },
        )

        assert response.status_code == 200, response.text

        access_token = response.json()["access_token"]

        return {
            "user_id": user_id,
            "account_id": account_id,
            "password": password,
            "access_token": access_token,
            "headers": {
                "Authorization": f"Bearer {access_token}",
            },
        }

    yield create_account

    # 테스트에서 생성한 사용자만 삭제
    with SessionLocal() as db:
        try:
            for account_id in created_account_ids:
                user = db.scalar(
                    select(User).where(
                        User.account_id == account_id
                    )
                )

                if user is None:
                    continue

                # FK 제약조건을 고려해 세션 먼저 삭제
                db.execute(
                    delete(UserSession).where(
                        UserSession.user_id == user.id
                    )
                )

                db.delete(user)

            db.commit()

        except Exception:
            db.rollback()
            raise


# -------------------------
# S3 서비스 모킹
# -------------------------

@pytest.fixture
def mock_s3(monkeypatch):
    user_router = importlib.import_module("app.routers.user")

    uploaded_keys = []
    deleted_keys = []

    def fake_upload_image(file, folder, owner_id):
        key = (
            f"{folder}/{owner_id}/"
            f"{uuid.uuid4().hex}.jpg"
        )
        uploaded_keys.append(key)
        return key

    def fake_generate_image_url(object_key):
        return f"https://example.com/{object_key}"

    def fake_delete_image(object_key):
        deleted_keys.append(object_key)

    monkeypatch.setattr(
        user_router,
        "upload_image",
        fake_upload_image,
    )

    monkeypatch.setattr(
        user_router,
        "generate_image_url",
        fake_generate_image_url,
    )

    monkeypatch.setattr(
        user_router,
        "delete_image",
        fake_delete_image,
    )

    return {
        "uploaded_keys": uploaded_keys,
        "deleted_keys": deleted_keys,
    }


# -------------------------
# 1. 내 프로필 조회
# -------------------------

def test_get_my_profile(client, account_factory):
    account = account_factory()

    response = client.get(
        "/users/me",
        headers=account["headers"],
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["id"] == account["user_id"]
    assert data["account_id"] == account["account_id"]
    assert data["is_active"] is True
    assert data["profile_image_url"] is None
    assert "created_at" in data
    assert "updated_at" in data

    print("[PASS] 내 프로필 조회")

    # 인증 없이 요청
    response = client.get("/users/me")

    assert response.status_code == 401

    print("[PASS] 인증되지 않은 프로필 조회 차단")


# -------------------------
# 2. 특정 사용자 프로필 조회
# -------------------------

def test_get_user_profile(client, account_factory):
    account = account_factory()
    user_id = account["user_id"]

    response = client.get(f"/users/{user_id}")

    assert response.status_code == 200, response.text
    assert response.json()["id"] == user_id

    print("[PASS] 특정 사용자 프로필 조회")

    # 존재하지 않는 사용자
    response = client.get("/users/999999999")

    assert response.status_code == 404

    print("[PASS] 존재하지 않는 사용자 조회 차단")

    # 탈퇴한 사용자 조회
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user is not None

        user.is_active = False
        db.commit()

    response = client.get(f"/users/{user_id}")

    assert response.status_code == 404

    print("[PASS] 비활성화된 사용자 조회 차단")


# -------------------------
# 3. 프로필 수정 및 updated_at 갱신
# -------------------------

def test_update_my_profile(client, account_factory):
    account = account_factory()

    before_response = client.get(
        "/users/me",
        headers=account["headers"],
    )

    assert before_response.status_code == 200
    before = before_response.json()

    response = client.patch(
        "/users/me",
        headers=account["headers"],
        data={
            "username": "agent_cs_test",
            "email": (
                f"user_{uuid.uuid4().hex[:12]}"
                "@example.com"
            ),
            "bio": "User API 자동화 테스트",
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["username"] == "agent_cs_test"
    assert data["bio"] == "User API 자동화 테스트"
    assert data["email"].endswith("@example.com")
    assert data["created_at"] == before["created_at"]
    assert data["updated_at"] >= before["updated_at"]

    print("[PASS] 프로필 정보 수정")
    print("[PASS] created_at 유지 및 updated_at 갱신 확인")

    # bio만 수정하고 나머지 필드는 유지되는지 확인
    previous_email = data["email"]

    response = client.patch(
        "/users/me",
        headers=account["headers"],
        data={
            "bio": "자기소개만 변경",
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["bio"] == "자기소개만 변경"
    assert data["username"] == "agent_cs_test"
    assert data["email"] == previous_email

    print("[PASS] 미전달 필드 기존 값 유지")

    # bio 삭제
    response = client.patch(
        "/users/me",
        headers=account["headers"],
        data={
            "bio": "null",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["bio"] is None

    print("[PASS] 자기소개 삭제")


# -------------------------
# 4. 프로필 수정 입력값 검증
# -------------------------

def test_update_profile_validation(client, account_factory):
    account = account_factory()
    headers = account["headers"]

    # username 최대 길이 초과
    response = client.patch(
        "/users/me",
        headers=headers,
        data={
            "username": "a" * 31,
        },
    )

    assert response.status_code == 422

    print("[PASS] 닉네임 길이 검증")

    # 잘못된 이메일
    response = client.patch(
        "/users/me",
        headers=headers,
        data={
            "email": "invalid-email",
        },
    )

    assert response.status_code == 422

    print("[PASS] 이메일 형식 검증")

    # bio 최대 길이 초과
    response = client.patch(
        "/users/me",
        headers=headers,
        data={
            "bio": "a" * 501,
        },
    )

    assert response.status_code == 422

    print("[PASS] 자기소개 길이 검증")

    # username에 null 입력
    response = client.patch(
        "/users/me",
        headers=headers,
        data={
            "username": "null",
        },
    )

    assert response.status_code == 422

    print("[PASS] 닉네임 null 변경 차단")

    # 인증 없이 수정
    response = client.patch(
        "/users/me",
        data={
            "username": "unauthorized",
        },
    )

    assert response.status_code == 401

    print("[PASS] 인증되지 않은 프로필 수정 차단")


# -------------------------
# 5. 이메일 중복 검사
# -------------------------

def test_duplicate_email(client, account_factory):
    account_1 = account_factory()
    account_2 = account_factory()

    shared_email = (
        f"duplicate_{uuid.uuid4().hex[:12]}"
        "@example.com"
    )

    # 첫 번째 사용자에게 이메일 설정
    response = client.patch(
        "/users/me",
        headers=account_1["headers"],
        data={
            "email": shared_email,
        },
    )

    assert response.status_code == 200, response.text

    # 두 번째 사용자가 같은 이메일 사용 시도
    response = client.patch(
        "/users/me",
        headers=account_2["headers"],
        data={
            "email": shared_email,
        },
    )

    assert response.status_code == 409, response.text

    print("[PASS] 중복 이메일 변경 차단")


# -------------------------
# 6. 프로필 이미지 업로드 및 교체
# -------------------------

def test_profile_image_upload_and_replace(
    client,
    account_factory,
    mock_s3,
):
    account = account_factory()
    user_id = account["user_id"]
    headers = account["headers"]

    # 첫 번째 이미지 업로드
    response = client.patch(
        "/users/me",
        headers=headers,
        files={
            "profile_image": (
                "first.jpg",
                b"fake-image-content-1",
                "image/jpeg",
            ),
        },
    )

    assert response.status_code == 200, response.text

    first_key = mock_s3["uploaded_keys"][0]

    assert response.json()["profile_image_url"] == (
        f"https://example.com/{first_key}"
    )

    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.profile_image_url == first_key

    print("[PASS] 프로필 이미지 업로드")

    # 두 번째 이미지로 교체
    response = client.patch(
        "/users/me",
        headers=headers,
        files={
            "profile_image": (
                "second.jpg",
                b"fake-image-content-2",
                "image/jpeg",
            ),
        },
    )

    assert response.status_code == 200, response.text

    second_key = mock_s3["uploaded_keys"][1]

    assert first_key != second_key

    assert response.json()["profile_image_url"] == (
        f"https://example.com/{second_key}"
    )

    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.profile_image_url == second_key

    # 기존 이미지 삭제 함수 호출 확인
    assert first_key in mock_s3["deleted_keys"]
    assert second_key not in mock_s3["deleted_keys"]

    print("[PASS] 프로필 이미지 교체")
    print("[PASS] 기존 S3 이미지 삭제 호출")


# -------------------------
# 7. 특정 사용자의 게시글 목록
# -------------------------

def test_get_user_posts(client, account_factory):
    account = account_factory()
    user_id = account["user_id"]

    response = client.get(
        f"/users/{user_id}/posts"
    )

    assert response.status_code == 200, response.text
    assert response.json() == []

    print("[PASS] 게시글이 없는 사용자 목록 조회")

    response = client.get(
        "/users/999999999/posts"
    )

    assert response.status_code == 404

    print("[PASS] 존재하지 않는 사용자 게시글 조회 차단")


# -------------------------
# 8. 좋아요한 게시글 목록
# -------------------------

def test_get_user_liked_posts(client, account_factory):
    account = account_factory()
    user_id = account["user_id"]

    response = client.get(
        f"/users/{user_id}/likes/posts"
    )

    assert response.status_code == 200, response.text
    assert response.json() == []

    print("[PASS] 좋아요한 게시글이 없는 사용자 조회")

    response = client.get(
        "/users/999999999/likes/posts"
    )

    assert response.status_code == 404

    print("[PASS] 존재하지 않는 사용자 좋아요 목록 조회 차단")
