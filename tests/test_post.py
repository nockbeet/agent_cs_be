
import io
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.session import Session as UserSession
from app.models.post import Post
from app.models.post_image import PostImage
from app.models.post_like import PostLike
from app.models.post_tag import PostTag
from app.models.tag import Tag
from app.models.comment import Comment
from app.routers import post as post_router
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

# -------------------------
# 테스트 클라이언트
# -------------------------

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


# -------------------------
# 테스트 계정 및 DB 정리
# -------------------------

@pytest.fixture
def test_accounts(client):
    unique = uuid.uuid4().hex[:12]

    accounts = [
        {
            "account_id": f"posttest_{unique}_a",
            "password": "testpassword123",
        },
        {
            "account_id": f"posttest_{unique}_b",
            "password": "testpassword123",
        },
    ]

    created_ids = []
    result = []

    try:
        for account in accounts:
            signup = client.post(
                "/auth/signup",
                json=account,
            )
            assert signup.status_code == 201, signup.text

            user_id = signup.json()["user_id"]
            created_ids.append(user_id)

            login = client.post(
                "/auth/login",
                json=account,
            )
            assert login.status_code == 200, login.text

            token = login.json()["access_token"]

            result.append({
                "user_id": user_id,
                "account_id": account["account_id"],
                "headers": {
                    "Authorization": f"Bearer {token}"
                },
            })

        yield result

    finally:
        if created_ids:
            with SessionLocal() as db:
                post_ids = select(Post.id).where(
                    Post.user_id.in_(created_ids)
                )

                # FK 참조 테이블부터 정리
                db.execute(
                    delete(Comment).where(
                        Comment.post_id.in_(post_ids)
                    )
                )
                db.execute(
                    delete(PostLike).where(
                        PostLike.post_id.in_(post_ids)
                    )
                )
                db.execute(
                    delete(PostLike).where(
                        PostLike.user_id.in_(created_ids)
                    )
                )
                db.execute(
                    delete(PostImage).where(
                        PostImage.post_id.in_(post_ids)
                    )
                )
                db.execute(
                    delete(PostTag).where(
                        PostTag.post_id.in_(post_ids)
                    )
                )
                db.execute(
                    delete(Post).where(
                        Post.user_id.in_(created_ids)
                    )
                )
                db.execute(
                    delete(UserSession).where(
                        UserSession.user_id.in_(created_ids)
                    )
                )
                db.execute(
                    delete(User).where(
                        User.id.in_(created_ids)
                    )
                )

                # 테스트에서만 생성한 태그 정리
                db.execute(
                    delete(Tag).where(
                        Tag.name.like(f"posttest_{unique}%"),
                        ~Tag.id.in_(
                            select(PostTag.tag_id)
                        ),
                    )
                )

                db.commit()


# -------------------------
# S3 모의 처리
# -------------------------

@pytest.fixture
def mock_s3(monkeypatch):
    uploaded = []
    deleted = []

    def fake_upload_image(file, folder, owner_id):
        key = (
            f"{folder}/{owner_id}/"
            f"{uuid.uuid4().hex}.png"
        )
        uploaded.append(key)
        return key

    def fake_generate_image_url(object_key):
        return f"https://example.com/{object_key}"

    def fake_delete_image(object_key):
        deleted.append(object_key)

    monkeypatch.setattr(
        post_router,
        "upload_image",
        fake_upload_image,
    )
    monkeypatch.setattr(
        post_router,
        "generate_image_url",
        fake_generate_image_url,
    )
    monkeypatch.setattr(
        post_router,
        "delete_image",
        fake_delete_image,
    )

    return {
        "uploaded": uploaded,
        "deleted": deleted,
    }


# -------------------------
# 공통 게시글 생성 함수
# -------------------------

def create_test_post(
    client,
    headers,
    title="테스트 게시글",
    content="테스트 본문입니다.",
    hashtags=None,
):
    data = {
        "title": title,
        "content": content,
    }

    if hashtags:
        data["hashtags"] = hashtags

    response = client.post(
        "/posts",
        headers=headers,
        data=data,
    )

    assert response.status_code == 201, response.text
    return response.json()


# -------------------------
# 1. 게시글 작성
# -------------------------

def test_create_post(client, test_accounts, mock_s3):
    user = test_accounts[0]

    post = create_test_post(
        client,
        user["headers"],
        title="Python 테스트",
        content="게시글 작성 테스트",
    )

    assert post["title"] == "Python 테스트"
    assert post["content"] == "게시글 작성 테스트"
    assert post["author_id"] == user["user_id"]
    assert post["like_count"] == 0
    assert post["comment_count"] == 0
    assert post["view_count"] == 0
    assert post["images"] == []
    assert post["is_deleted"] is False


# -------------------------
# 2. 인증 없는 게시글 작성
# -------------------------

def test_create_post_without_auth(client):
    response = client.post(
        "/posts",
        data={
            "title": "인증 없는 게시글",
            "content": "작성되면 안 됩니다.",
        },
    )

    assert response.status_code == 401


# -------------------------
# 3. 제목과 본문 유효성 검사
# -------------------------

@pytest.mark.parametrize(
    "title, content",
    [
        ("", "정상 본문"),
        ("   ", "정상 본문"),
        ("정상 제목", "   "),
        ("a" * 201, "정상 본문"),
    ],
)
def test_create_post_invalid_data(
    client,
    test_accounts,
    title,
    content,
):
    response = client.post(
        "/posts",
        headers=test_accounts[0]["headers"],
        data={
            "title": title,
            "content": content,
        },
    )

    assert response.status_code == 422


# -------------------------
# 4. 해시태그 정규화 및 중복 제거
# -------------------------

def test_create_post_hashtags(
    client,
    test_accounts,
    mock_s3,
):
    tag_name = f"posttest_{uuid.uuid4().hex[:12]}"

    response = client.post(
        "/posts",
        headers=test_accounts[0]["headers"],
        data={
        "title": "태그 테스트",
        "content": "태그 중복 확인",
        "hashtags": [tag_name.upper(), tag_name],
        },
    )

    assert response.status_code == 201, response.text

    hashtags = response.json()["hashtags"]

    assert len(hashtags) == 1
    assert hashtags[0]["name"] == tag_name


# -------------------------
# 5. 여러 이미지 업로드
# -------------------------

def test_create_post_multiple_images(
    client,
    test_accounts,
    mock_s3,
):
    content = (
        "첫 번째 이미지\n"
        "![이미지1](upload://img_1)\n\n"
        "두 번째 이미지\n"
        "![이미지2](upload://img_2)"
    )

    response = client.post(
        "/posts",
        headers=test_accounts[0]["headers"],
        data={
        "title": "다중 이미지 테스트",
        "content": content,
        "image_ids": ["img_1", "img_2"],
        },
        files=[
            (
                "images",
                ("first.png", io.BytesIO(b"first"), "image/png"),
            ),
            (
                "images",
                ("second.png", io.BytesIO(b"second"), "image/png"),
            ),
        ],
    )

    assert response.status_code == 201, response.text

    result = response.json()

    assert len(result["images"]) == 2
    assert len(mock_s3["uploaded"]) == 2
    assert "upload://" not in result["content"]
    assert "https://example.com/posts/" in result["content"]

    with SessionLocal() as db:
        saved = db.scalars(
            select(PostImage).where(
                PostImage.post_id == result["id"]
            )
        ).all()

        assert len(saved) == 2
        assert all(
            image.image_url.startswith("posts/")
            for image in saved
        )


# -------------------------
# 6. 이미지 ID 불일치
# -------------------------

def test_create_post_image_id_mismatch(
    client,
    test_accounts,
    mock_s3,
):
    response = client.post(
        "/posts",
        headers=test_accounts[0]["headers"],
        data={
            "title": "이미지 ID 오류",
            "content": "![이미지](upload://img_1)",
            "image_ids": "img_2",
        },
        files={
            "images": (
                "test.png",
                io.BytesIO(b"test"),
                "image/png",
            )
        },
    )

    assert response.status_code == 422
    assert mock_s3["uploaded"] == []


# -------------------------
# 7. 목록 조회, 검색, 정렬
# -------------------------

def test_get_posts_filter_and_sort(
    client,
    test_accounts,
    mock_s3,
):
    unique = uuid.uuid4().hex[:12]
    tag_name = f"posttest_{unique}"

    first = create_test_post(
        client,
        test_accounts[0]["headers"],
        title=f"{unique} Python 첫 번째",
        hashtags=[tag_name],
    )

    second = create_test_post(
        client,
        test_accounts[0]["headers"],
        title=f"{unique} FastAPI 두 번째",
        hashtags=[tag_name],
    )

    response = client.get(
        "/posts",
        params={
            "title": unique,
            "tag": tag_name,
        },
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids == [second["id"], first["id"]]

    client.get(f"/posts/{first['id']}")
    client.get(f"/posts/{first['id']}")

    sorted_response = client.get(
        "/posts",
        params={
            "title": unique,
            "sort": "view_count",
        },
    )

    assert sorted_response.status_code == 200
    assert sorted_response.json()[0]["id"] == first["id"]


# -------------------------
# 8. 상세 조회 시 조회수 증가
# -------------------------

def test_get_post_increases_view_count(
    client,
    test_accounts,
    mock_s3,
):
    post = create_test_post(
        client,
        test_accounts[0]["headers"],
    )

    first = client.get(f"/posts/{post['id']}")
    second = client.get(f"/posts/{post['id']}")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["view_count"] == 1
    assert second.json()["view_count"] == 2


# -------------------------
# 9. 존재하지 않는 게시글 조회
# -------------------------

def test_get_nonexistent_post(client):
    response = client.get("/posts/999999999")

    assert response.status_code == 404


# -------------------------
# 10. 게시글 수정
# -------------------------

def test_update_post(client, test_accounts, mock_s3):
    post = create_test_post(
        client,
        test_accounts[0]["headers"],
    )

    response = client.patch(
        f"/posts/{post['id']}",
        headers=test_accounts[0]["headers"],
        data={
            "title": "수정된 제목",
            "content": "수정된 본문",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "수정된 제목"
    assert response.json()["content"] == "수정된 본문"


# -------------------------
# 11. 태그 전체 제거
# -------------------------

def test_update_post_remove_tags(
    client,
    test_accounts,
    mock_s3,
):
    tag_name = f"posttest_{uuid.uuid4().hex[:12]}"

    post = create_test_post(
        client,
        test_accounts[0]["headers"],
        hashtags=[tag_name],
    )

    response = client.patch(
        f"/posts/{post['id']}",
        headers=test_accounts[0]["headers"],
        data={"hashtags": "[]"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["hashtags"] == []


# -------------------------
# 12. 다른 사용자의 게시글 수정 금지
# -------------------------

def test_update_post_forbidden(
    client,
    test_accounts,
    mock_s3,
):
    owner, other = test_accounts

    post = create_test_post(
        client,
        owner["headers"],
    )

    response = client.patch(
        f"/posts/{post['id']}",
        headers=other["headers"],
        data={"title": "다른 사용자의 수정"},
    )

    assert response.status_code == 403


# -------------------------
# 13. 좋아요 등록 및 중복 방지
# -------------------------

def test_like_post(client, test_accounts, mock_s3):
    post = create_test_post(
        client,
        test_accounts[0]["headers"],
    )

    url = f"/posts/{post['id']}/likes"

    first = client.post(
        url,
        headers=test_accounts[0]["headers"],
    )
    second = client.post(
        url,
        headers=test_accounts[0]["headers"],
    )

    assert first.status_code == 200
    assert first.json()["like_count"] == 1
    assert first.json()["is_liked"] is True

    assert second.status_code == 409

    with SessionLocal() as db:
        likes = db.scalars(
            select(PostLike).where(
                PostLike.post_id == post["id"]
            )
        ).all()

        assert len(likes) == 1


# -------------------------
# 14. 좋아요 취소 및 중복 취소 방지
# -------------------------

def test_unlike_post(client, test_accounts, mock_s3):
    post = create_test_post(
        client,
        test_accounts[0]["headers"],
    )

    url = f"/posts/{post['id']}/likes"
    headers = test_accounts[0]["headers"]

    client.post(url, headers=headers)

    first = client.delete(url, headers=headers)
    second = client.delete(url, headers=headers)

    assert first.status_code == 200
    assert first.json()["like_count"] == 0
    assert first.json()["is_liked"] is False

    assert second.status_code == 404


# -------------------------
# 15. 게시글 Soft Delete
# -------------------------

def test_delete_post(client, test_accounts, mock_s3):
    post = create_test_post(
        client,
        test_accounts[0]["headers"],
    )

    response = client.delete(
        f"/posts/{post['id']}",
        headers=test_accounts[0]["headers"],
    )

    assert response.status_code == 200

    with SessionLocal() as db:
        saved = db.get(Post, post["id"])
        assert saved is not None
        assert saved.is_deleted is True

    detail = client.get(f"/posts/{post['id']}")
    assert detail.status_code == 404

    listing = client.get(
        "/posts",
        params={"title": post["title"]},
    )
    assert listing.status_code == 200
    assert all(
        item["id"] != post["id"]
        for item in listing.json()
    )


# -------------------------
# 16. 다른 사용자의 게시글 삭제 금지
# -------------------------

def test_delete_post_forbidden(
    client,
    test_accounts,
    mock_s3,
):
    owner, other = test_accounts

    post = create_test_post(
        client,
        owner["headers"],
    )

    response = client.delete(
        f"/posts/{post['id']}",
        headers=other["headers"],
    )

    assert response.status_code == 403

    with SessionLocal() as db:
        saved = db.get(Post, post["id"])
        assert saved.is_deleted is False

# -------------------------
# 17. 게시글 삭제 + 댓글 작성 동시성
# -------------------------

def test_concurrent_delete_post_and_create_comment(
    client,
    test_accounts,
    mock_s3,
):
    owner, other = test_accounts

    post = create_test_post(
        client,
        owner["headers"],
    )
    post_id = post["id"]

    barrier = Barrier(2)

    def delete_request():
        barrier.wait()
        return client.delete(
            f"/posts/{post_id}",
            headers=owner["headers"],
        )

    def comment_request():
        barrier.wait()
        return client.post(
            f"/posts/{post_id}/comments",
            headers=other["headers"],
            json={"content": "동시성 테스트 댓글"},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        delete_future = executor.submit(delete_request)
        comment_future = executor.submit(comment_request)

        delete_response = delete_future.result()
        comment_response = comment_future.result()

    assert delete_response.status_code == 200
    assert comment_response.status_code in (201, 404)

    with SessionLocal() as db:
        saved_post = db.get(Post, post_id)

        comments = db.scalars(
            select(Comment).where(
                Comment.post_id == post_id,
            )
        ).all()

        assert saved_post.is_deleted is True

        if comment_response.status_code == 201:
            assert len(comments) == 1
            assert saved_post.comment_count == 1
        else:
            assert len(comments) == 0
            assert saved_post.comment_count == 0
            
# -------------------------
# 18. 게시글 삭제 + 대댓글 작성 동시성
# -------------------------

def test_concurrent_delete_post_and_create_reply(
    client,
    test_accounts,
    mock_s3,
):
    owner, other = test_accounts

    post = create_test_post(
        client,
        owner["headers"],
    )
    post_id = post["id"]

    parent_response = client.post(
        f"/posts/{post_id}/comments",
        headers=owner["headers"],
        json={"content": "부모 댓글"},
    )

    assert parent_response.status_code == 201, parent_response.text
    parent_id = parent_response.json()["id"]

    barrier = Barrier(2)

    def delete_request():
        barrier.wait()
        return client.delete(
            f"/posts/{post_id}",
            headers=owner["headers"],
        )

    def reply_request():
        barrier.wait()
        return client.post(
            f"/comments/{parent_id}/replies",
            headers=other["headers"],
            json={"content": "동시성 테스트 대댓글"},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        delete_future = executor.submit(delete_request)
        reply_future = executor.submit(reply_request)

        delete_response = delete_future.result()
        reply_response = reply_future.result()

    assert delete_response.status_code == 200
    assert reply_response.status_code in (201, 404)

    with SessionLocal() as db:
        saved_post = db.get(Post, post_id)

        comments = db.scalars(
            select(Comment).where(
                Comment.post_id == post_id,
            )
        ).all()

        assert saved_post.is_deleted is True

        if reply_response.status_code == 201:
            assert len(comments) == 2
            assert saved_post.comment_count == 2
        else:
            assert len(comments) == 1
            assert saved_post.comment_count == 1
            
# -------------------------
# 19. 게시글 삭제 + 좋아요 등록 동시성
# -------------------------

def test_concurrent_delete_post_and_like(
    client,
    test_accounts,
    mock_s3,
):
    owner, other = test_accounts

    post = create_test_post(
        client,
        owner["headers"],
    )
    post_id = post["id"]

    barrier = Barrier(2)

    def delete_request():
        barrier.wait()
        return client.delete(
            f"/posts/{post_id}",
            headers=owner["headers"],
        )

    def like_request():
        barrier.wait()
        return client.post(
            f"/posts/{post_id}/likes",
            headers=other["headers"],
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        delete_future = executor.submit(delete_request)
        like_future = executor.submit(like_request)

        delete_response = delete_future.result()
        like_response = like_future.result()

    assert delete_response.status_code == 200
    assert like_response.status_code in (200, 404)

    with SessionLocal() as db:
        saved_post = db.get(Post, post_id)

        likes = db.scalars(
            select(PostLike).where(
                PostLike.post_id == post_id,
            )
        ).all()

        assert saved_post.is_deleted is True

        if like_response.status_code == 200:
            assert len(likes) == 1
            assert saved_post.like_count == 1
        else:
            assert len(likes) == 0
            assert saved_post.like_count == 0