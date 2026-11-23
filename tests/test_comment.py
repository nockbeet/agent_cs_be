
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.session import Session as UserSession
from app.models.post import Post
from app.models.comment import Comment
from app.routers import post as post_router
from app.routers import comment as comment_router
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
            "account_id": f"commenttest_{unique}_a",
            "password": "testpassword123",
        },
        {
            "account_id": f"commenttest_{unique}_b",
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

            result.append({
                "user_id": user_id,
                "account_id": account["account_id"],
                "headers": {
                    "Authorization": (
                        f"Bearer {login.json()['access_token']}"
                    )
                },
            })

        yield result

    finally:
        if created_ids:
            with SessionLocal() as db:
                post_ids = select(Post.id).where(
                    Post.user_id.in_(created_ids)
                )

                # 대댓글부터 삭제 (자기 참조 FK)
                db.execute(
                    delete(Comment).where(
                        Comment.post_id.in_(post_ids),
                        Comment.parent_comment_id.is_not(None),
                    )
                )

                # 부모 댓글 삭제
                db.execute(
                    delete(Comment).where(
                        Comment.post_id.in_(post_ids)
                    )
                )

                # 테스트 게시글 삭제
                db.execute(
                    delete(Post).where(
                        Post.user_id.in_(created_ids)
                    )
                )

                # 세션 삭제
                db.execute(
                    delete(UserSession).where(
                        UserSession.user_id.in_(created_ids)
                    )
                )

                # 테스트 계정 삭제
                db.execute(
                    delete(User).where(
                        User.id.in_(created_ids)
                    )
                )

                db.commit()


# -------------------------
# S3 모의 처리
# -------------------------

@pytest.fixture
def mock_s3(monkeypatch):
    def fake_generate_image_url(object_key):
        return f"https://example.com/{object_key}"

    monkeypatch.setattr(
        comment_router,
        "generate_image_url",
        fake_generate_image_url,
    )

    monkeypatch.setattr(
        post_router,
        "generate_image_url",
        fake_generate_image_url,
    )


# -------------------------
# 공통 테스트 데이터 생성 함수
# -------------------------

def create_test_post(
    client,
    headers,
):
    response = client.post(
        "/posts",
        headers=headers,
        data={
            "title": "댓글 테스트 게시글",
            "content": "댓글 테스트용 본문입니다.",
        },
    )

    assert response.status_code == 201, response.text
    return response.json()


def create_test_comment(
    client,
    post_id,
    headers,
    content="테스트 댓글입니다.",
):
    response = client.post(
        f"/posts/{post_id}/comments",
        headers=headers,
        json={"content": content},
    )

    assert response.status_code == 201, response.text
    return response.json()


def create_test_reply(
    client,
    post_id,
    comment_id,
    headers,
    content="테스트 대댓글입니다.",
):
    response = client.post(
        f"/posts/{post_id}/comments/{comment_id}/replies",
        headers=headers,
        json={"content": content},
    )

    assert response.status_code == 201, response.text
    return response.json()


def get_comment_count(post_id):
    with SessionLocal() as db:
        post = db.get(Post, post_id)
        assert post is not None
        return post.comment_count


# -------------------------
# 1. 댓글 작성
# -------------------------

def test_create_comment(client, test_accounts, mock_s3):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])

    comment = create_test_comment(
        client,
        post["id"],
        user["headers"],
        content="첫 번째 댓글입니다.",
    )

    assert comment["post_id"] == post["id"]
    assert comment["content"] == "첫 번째 댓글입니다."
    assert comment["author_id"] == user["user_id"]
    assert comment["author_account_id"] == user["account_id"]
    assert comment["parent_comment_id"] is None
    assert comment["replies"] == []
    assert comment["is_deleted"] is False

    assert get_comment_count(post["id"]) == 1


# -------------------------
# 2. 인증 없는 댓글 작성
# -------------------------

def test_create_comment_without_auth(
    client,
    test_accounts,
    mock_s3,
):
    post = create_test_post(
        client,
        test_accounts[0]["headers"],
    )

    response = client.post(
        f"/posts/{post['id']}/comments",
        json={"content": "인증 없는 댓글"},
    )

    assert response.status_code == 401
    assert get_comment_count(post["id"]) == 0


# -------------------------
# 3. 댓글 내용 유효성 검사
# -------------------------

@pytest.mark.parametrize(
    "content",
    [
        "",
        "   ",
        "a" * 5001,
    ],
)
def test_create_comment_invalid_content(
    client,
    test_accounts,
    mock_s3,
    content,
):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])

    response = client.post(
        f"/posts/{post['id']}/comments",
        headers=user["headers"],
        json={"content": content},
    )

    assert response.status_code == 422
    assert get_comment_count(post["id"]) == 0


# -------------------------
# 4. 댓글 최대 길이 5000자 허용
# -------------------------

def test_create_comment_max_length(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])

    comment = create_test_comment(
        client,
        post["id"],
        user["headers"],
        content="a" * 5000,
    )

    assert len(comment["content"]) == 5000


# -------------------------
# 5. 댓글 목록 조회
# -------------------------

def test_get_comments(client, test_accounts, mock_s3):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])

    first = create_test_comment(
        client,
        post["id"],
        user["headers"],
        content="첫 번째 댓글",
    )

    second = create_test_comment(
        client,
        post["id"],
        user["headers"],
        content="두 번째 댓글",
    )

    response = client.get(
        f"/posts/{post['id']}/comments"
    )

    assert response.status_code == 200, response.text

    comments = response.json()

    assert len(comments) == 2
    assert [item["id"] for item in comments] == [
        first["id"],
        second["id"],
    ]


# -------------------------
# 6. 댓글이 없는 게시글 조회
# -------------------------

def test_get_comments_empty(
    client,
    test_accounts,
    mock_s3,
):
    post = create_test_post(
        client,
        test_accounts[0]["headers"],
    )

    response = client.get(
        f"/posts/{post['id']}/comments"
    )

    assert response.status_code == 200
    assert response.json() == []


# -------------------------
# 7. 대댓글 작성 및 트리 구조
# -------------------------

def test_create_reply_and_tree(
    client,
    test_accounts,
    mock_s3,
):
    owner, other = test_accounts
    post = create_test_post(client, owner["headers"])

    parent = create_test_comment(
        client,
        post["id"],
        owner["headers"],
    )

    reply = create_test_reply(
        client,
        post["id"],
        parent["id"],
        other["headers"],
    )

    assert reply["parent_comment_id"] == parent["id"]
    assert reply["author_id"] == other["user_id"]
    assert reply["replies"] == []

    response = client.get(
        f"/posts/{post['id']}/comments"
    )

    assert response.status_code == 200

    comments = response.json()

    assert len(comments) == 1
    assert comments[0]["id"] == parent["id"]
    assert len(comments[0]["replies"]) == 1
    assert comments[0]["replies"][0]["id"] == reply["id"]

    assert get_comment_count(post["id"]) == 2


# -------------------------
# 8. 대댓글에 추가 대댓글 작성 금지
# -------------------------

def test_reply_depth_limit(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])

    parent = create_test_comment(
        client,
        post["id"],
        user["headers"],
    )

    reply = create_test_reply(
        client,
        post["id"],
        parent["id"],
        user["headers"],
    )

    response = client.post(
        f"/posts/{post['id']}/comments/{reply['id']}/replies",
        headers=user["headers"],
        json={"content": "3단계 댓글"},
    )

    assert response.status_code == 400
    assert get_comment_count(post["id"]) == 2


# -------------------------
# 9. 댓글 수정
# -------------------------

def test_update_comment(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])

    comment = create_test_comment(
        client,
        post["id"],
        user["headers"],
    )

    response = client.patch(
        f"/posts/{post['id']}/comments/{comment['id']}",
        headers=user["headers"],
        json={"content": "수정된 댓글입니다."},
    )

    assert response.status_code == 200, response.text
    assert response.json()["content"] == "수정된 댓글입니다."

    with SessionLocal() as db:
        saved = db.get(Comment, comment["id"])
        assert saved.content == "수정된 댓글입니다."

    assert get_comment_count(post["id"]) == 1


# -------------------------
# 10. 다른 사용자의 댓글 수정 금지
# -------------------------

def test_update_comment_forbidden(
    client,
    test_accounts,
    mock_s3,
):
    owner, other = test_accounts
    post = create_test_post(client, owner["headers"])

    comment = create_test_comment(
        client,
        post["id"],
        owner["headers"],
    )

    response = client.patch(
        f"/posts/{post['id']}/comments/{comment['id']}",
        headers=other["headers"],
        json={"content": "다른 사용자의 수정"},
    )

    assert response.status_code == 403

    with SessionLocal() as db:
        saved = db.get(Comment, comment["id"])
        assert saved.content == "테스트 댓글입니다."


# -------------------------
# 11. 댓글 수정 유효성 검사
# -------------------------

@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"content": None},
        {"content": ""},
        {"content": "   "},
        {"content": "a" * 5001},
    ],
)
def test_update_comment_invalid_content(
    client,
    test_accounts,
    mock_s3,
    payload,
):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])

    comment = create_test_comment(
        client,
        post["id"],
        user["headers"],
    )

    response = client.patch(
        f"/posts/{post['id']}/comments/{comment['id']}",
        headers=user["headers"],
        json=payload,
    )

    assert response.status_code == 422


# -------------------------
# 12. 댓글 Soft Delete
# -------------------------

def test_delete_comment(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])

    comment = create_test_comment(
        client,
        post["id"],
        user["headers"],
    )

    response = client.delete(
        f"/posts/{post['id']}/comments/{comment['id']}",
        headers=user["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["message"] == "댓글이 삭제되었습니다."

    with SessionLocal() as db:
        saved = db.get(Comment, comment["id"])

        assert saved is not None
        assert saved.is_deleted is True
        assert saved.content == "테스트 댓글입니다."

    listing = client.get(
        f"/posts/{post['id']}/comments"
    )

    deleted_comment = listing.json()[0]

    assert deleted_comment["id"] == comment["id"]
    assert deleted_comment["content"] is None
    assert deleted_comment["is_deleted"] is True

    assert get_comment_count(post["id"]) == 0


# -------------------------
# 13. 댓글 중복 삭제 방지
# -------------------------

def test_delete_comment_twice(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])

    comment = create_test_comment(
        client,
        post["id"],
        user["headers"],
    )

    url = (
        f"/posts/{post['id']}/comments/{comment['id']}"
    )

    first = client.delete(url, headers=user["headers"])
    second = client.delete(url, headers=user["headers"])

    assert first.status_code == 200
    assert second.status_code == 404

    assert get_comment_count(post["id"]) == 0


# -------------------------
# 14. 다른 사용자의 댓글 삭제 금지
# -------------------------

def test_delete_comment_forbidden(
    client,
    test_accounts,
    mock_s3,
):
    owner, other = test_accounts
    post = create_test_post(client, owner["headers"])

    comment = create_test_comment(
        client,
        post["id"],
        owner["headers"],
    )

    response = client.delete(
        f"/posts/{post['id']}/comments/{comment['id']}",
        headers=other["headers"],
    )

    assert response.status_code == 403

    with SessionLocal() as db:
        saved = db.get(Comment, comment["id"])
        assert saved.is_deleted is False

    assert get_comment_count(post["id"]) == 1


# -------------------------
# 15. 삭제된 부모 댓글의 대댓글 유지
# -------------------------

def test_deleted_parent_keeps_replies(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])

    parent = create_test_comment(
        client,
        post["id"],
        user["headers"],
    )

    reply = create_test_reply(
        client,
        post["id"],
        parent["id"],
        user["headers"],
    )

    response = client.delete(
        f"/posts/{post['id']}/comments/{parent['id']}",
        headers=user["headers"],
    )

    assert response.status_code == 200

    listing = client.get(
        f"/posts/{post['id']}/comments"
    )

    assert listing.status_code == 200

    comments = listing.json()

    assert len(comments) == 1
    assert comments[0]["content"] is None
    assert comments[0]["is_deleted"] is True

    assert len(comments[0]["replies"]) == 1
    assert comments[0]["replies"][0]["id"] == reply["id"]
    assert comments[0]["replies"][0]["is_deleted"] is False

    assert get_comment_count(post["id"]) == 1


# -------------------------
# 16. 삭제된 부모 댓글에 대댓글 작성 금지
# -------------------------

def test_reply_to_deleted_parent(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])

    parent = create_test_comment(
        client,
        post["id"],
        user["headers"],
    )

    client.delete(
        f"/posts/{post['id']}/comments/{parent['id']}",
        headers=user["headers"],
    )

    response = client.post(
        f"/posts/{post['id']}/comments/{parent['id']}/replies",
        headers=user["headers"],
        json={"content": "삭제된 댓글에 답글"},
    )

    assert response.status_code == 404
    assert get_comment_count(post["id"]) == 0


# -------------------------
# 17. 다른 게시글의 댓글 ID 사용 금지
# -------------------------

def test_comment_post_id_mismatch(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]

    first_post = create_test_post(
        client,
        user["headers"],
    )

    second_post = create_test_post(
        client,
        user["headers"],
    )

    comment = create_test_comment(
        client,
        first_post["id"],
        user["headers"],
    )

    wrong_url = (
        f"/posts/{second_post['id']}/comments/{comment['id']}"
    )

    update_response = client.patch(
        wrong_url,
        headers=user["headers"],
        json={"content": "잘못된 게시글 ID"},
    )

    delete_response = client.delete(
        wrong_url,
        headers=user["headers"],
    )

    reply_response = client.post(
        f"{wrong_url}/replies",
        headers=user["headers"],
        json={"content": "잘못된 대댓글"},
    )

    assert update_response.status_code == 404
    assert delete_response.status_code == 404
    assert reply_response.status_code == 404

    assert get_comment_count(first_post["id"]) == 1
    assert get_comment_count(second_post["id"]) == 0


# -------------------------
# 18. 존재하지 않는 게시글
# -------------------------

def test_nonexistent_post(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]
    post_id = 999999999

    get_response = client.get(
        f"/posts/{post_id}/comments"
    )

    create_response = client.post(
        f"/posts/{post_id}/comments",
        headers=user["headers"],
        json={"content": "존재하지 않는 게시글"},
    )

    assert get_response.status_code == 404
    assert create_response.status_code == 404


# -------------------------
# 19. 삭제된 게시글에 댓글 작성 금지
# -------------------------

def test_comment_on_deleted_post(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])

    deleted = client.delete(
        f"/posts/{post['id']}",
        headers=user["headers"],
    )

    assert deleted.status_code == 200

    response = client.post(
        f"/posts/{post['id']}/comments",
        headers=user["headers"],
        json={"content": "삭제된 게시글에 댓글"},
    )

    assert response.status_code == 404
    assert get_comment_count(post["id"]) == 0


# -------------------------
# 20. 댓글 및 대댓글 수 갱신
# -------------------------

def test_comment_count_consistency(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]
    post = create_test_post(client, user["headers"])
    post_id = post["id"]

    assert get_comment_count(post_id) == 0

    first = create_test_comment(
        client,
        post_id,
        user["headers"],
    )
    assert get_comment_count(post_id) == 1

    second = create_test_comment(
        client,
        post_id,
        user["headers"],
    )
    assert get_comment_count(post_id) == 2

    reply = create_test_reply(
        client,
        post_id,
        first["id"],
        user["headers"],
    )
    assert get_comment_count(post_id) == 3

    client.delete(
        f"/posts/{post_id}/comments/{first['id']}",
        headers=user["headers"],
    )
    assert get_comment_count(post_id) == 2

    client.delete(
        f"/posts/{post_id}/comments/{reply['id']}",
        headers=user["headers"],
    )
    assert get_comment_count(post_id) == 1

    client.delete(
        f"/posts/{post_id}/comments/{second['id']}",
        headers=user["headers"],
    )
    assert get_comment_count(post_id) == 0

    with SessionLocal() as db:
        active_comments = db.scalars(
            select(Comment).where(
                Comment.post_id == post_id,
                Comment.is_deleted.is_(False),
            )
        ).all()

        assert len(active_comments) == 0


# -------------------------
# 동시성 테스트 공통 함수
# -------------------------

def run_concurrent_requests(request_a, request_b):
    """
    두 HTTP 요청을 가능한 한 동시에 시작한다.

    각 요청은 별도 스레드에서 실행하며,
    Barrier를 통해 시작 시점을 맞춘다.
    """
    barrier = Barrier(2, timeout=10)

    def run_request(request_func):
        barrier.wait()
        return request_func()

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(run_request, request_a)
        future_b = executor.submit(run_request, request_b)

        return future_a.result(), future_b.result()


# -------------------------
# 21. 동일 댓글 동시 삭제
# -------------------------

def test_concurrent_delete_same_comment(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]
    post = create_test_post(
        client,
        user["headers"],
    )

    comment = create_test_comment(
        client,
        post["id"],
        user["headers"],
    )

    url = (
        f"/posts/{post['id']}/comments/{comment['id']}"
    )

    def delete_request():
        return client.delete(
            url,
            headers=user["headers"],
        )

    first, second = run_concurrent_requests(
        delete_request,
        delete_request,
    )

    # 한 요청만 삭제에 성공해야 함
    assert sorted([
        first.status_code,
        second.status_code,
    ]) == [200, 404]

    # 댓글 수가 한 번만 감소해야 함
    assert get_comment_count(post["id"]) == 0

    with SessionLocal() as db:
        saved = db.get(Comment, comment["id"])

        assert saved is not None
        assert saved.is_deleted is True

        active_count = db.scalars(
            select(Comment).where(
                Comment.post_id == post["id"],
                Comment.is_deleted.is_(False),
            )
        ).all()

        assert len(active_count) == 0


# -------------------------
# 22. 부모 댓글 삭제와 대댓글 작성 동시 실행
# -------------------------

def test_concurrent_delete_parent_and_create_reply(
    client,
    test_accounts,
    mock_s3,
):
    owner, other = test_accounts

    post = create_test_post(
        client,
        owner["headers"],
    )

    parent = create_test_comment(
        client,
        post["id"],
        owner["headers"],
    )

    delete_url = (
        f"/posts/{post['id']}/comments/{parent['id']}"
    )

    reply_url = (
        f"/posts/{post['id']}/comments/"
        f"{parent['id']}/replies"
    )

    def delete_request():
        return client.delete(
            delete_url,
            headers=owner["headers"],
        )

    def reply_request():
        return client.post(
            reply_url,
            headers=other["headers"],
            json={
                "content": "동시에 작성한 대댓글",
            },
        )

    delete_response, reply_response = (
        run_concurrent_requests(
            delete_request,
            reply_request,
        )
    )

    # 부모 댓글 삭제는 성공해야 함
    assert delete_response.status_code == 200

    # 대댓글은 잠금 획득 순서에 따라
    # 성공하거나 삭제된 부모 댓글로 인해 실패
    assert reply_response.status_code in (201, 404)

    with SessionLocal() as db:
        saved_parent = db.get(
            Comment,
            parent["id"],
        )

        assert saved_parent is not None
        assert saved_parent.is_deleted is True

        replies = db.scalars(
            select(Comment).where(
                Comment.parent_comment_id == parent["id"]
            )
        ).all()

        if reply_response.status_code == 201:
            # 대댓글 작성이 먼저 완료된 경우
            assert len(replies) == 1
            assert replies[0].is_deleted is False
            expected_count = 1

        else:
            # 부모 댓글 삭제가 먼저 완료된 경우
            assert len(replies) == 0
            expected_count = 0

        saved_post = db.get(Post, post["id"])
        assert saved_post.comment_count == expected_count

    # 부모 댓글 삭제 후에는
    # 새로운 대댓글 작성이 반드시 차단되어야 함
    after_delete = client.post(
        reply_url,
        headers=other["headers"],
        json={
            "content": "삭제 후 추가 대댓글",
        },
    )

    assert after_delete.status_code == 404


# -------------------------
# 23. 동일 댓글 수정과 삭제 동시 실행
# -------------------------

def test_concurrent_update_and_delete_comment(
    client,
    test_accounts,
    mock_s3,
):
    user = test_accounts[0]

    post = create_test_post(
        client,
        user["headers"],
    )

    comment = create_test_comment(
        client,
        post["id"],
        user["headers"],
        content="수정 전 댓글",
    )

    url = (
        f"/posts/{post['id']}/comments/{comment['id']}"
    )

    def update_request():
        return client.patch(
            url,
            headers=user["headers"],
            json={
                "content": "동시에 수정된 댓글",
            },
        )

    def delete_request():
        return client.delete(
            url,
            headers=user["headers"],
        )

    update_response, delete_response = (
        run_concurrent_requests(
            update_request,
            delete_request,
        )
    )

    # 삭제 요청은 반드시 성공
    assert delete_response.status_code == 200

    # 수정이 먼저 완료되면 200,
    # 삭제가 먼저 완료되면 404
    assert update_response.status_code in (200, 404)

    with SessionLocal() as db:
        saved = db.get(
            Comment,
            comment["id"],
        )

        assert saved is not None
        assert saved.is_deleted is True

        if update_response.status_code == 200:
            assert saved.content == "동시에 수정된 댓글"
        else:
            assert saved.content == "수정 전 댓글"

        saved_post = db.get(Post, post["id"])
        assert saved_post.comment_count == 0

    # 삭제된 댓글은 이후 수정할 수 없어야 함
    after_delete = client.patch(
        url,
        headers=user["headers"],
        json={
            "content": "삭제 후 수정 시도",
        },
    )

    assert after_delete.status_code == 404
