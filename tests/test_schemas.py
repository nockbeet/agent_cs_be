
from pydantic import ValidationError

from app.schemas.auth import SignupRequest
from app.schemas.user import UserUpdateRequest
from app.schemas.tag import TagResponse
from app.schemas.post import (
    PostCreateRequest,
    PostUpdateRequest,
    PostDetailResponse,
)
from app.schemas.comment import (
    CommentCreateRequest,
    CommentUpdateRequest,
    CommentResponse,
)


def run_test(name, test_func):
    try:
        test_func()
        print(f"[PASS] {name}")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")


def expect_validation_error(schema, data):
    try:
        schema.model_validate(data)
    except ValidationError:
        return

    raise AssertionError("ValidationError가 발생해야 합니다.")


# -------------------------
# 1. 회원가입 검증
# -------------------------

def test_auth():
    valid = SignupRequest(
        account_id="user_123",
        password="password123"
    )
    assert valid.account_id == "user_123"

    expect_validation_error(
        SignupRequest,
        {"account_id": "abc", "password": "password123"}
    )

    expect_validation_error(
        SignupRequest,
        {"account_id": "User123", "password": "password123"}
    )

    expect_validation_error(
        SignupRequest,
        {"account_id": "user123", "password": "1234567"}
    )


# -------------------------
# 2. 사용자 프로필 수정
# -------------------------

def test_user():
    request = UserUpdateRequest(bio=None)

    data = request.model_dump(exclude_unset=True)
    assert data == {"bio": None}

    empty_request = UserUpdateRequest()
    assert empty_request.model_dump(exclude_unset=True) == {}

    expect_validation_error(
        UserUpdateRequest,
        {"username": None}
    )


# -------------------------
# 3. 태그 응답
# -------------------------

def test_tag():
    tag = TagResponse(id=1, name="python")

    assert tag.id == 1
    assert tag.name == "python"


# -------------------------
# 4. 게시글 작성 및 수정
# -------------------------

def test_post():
    post = PostCreateRequest(
        title="Python 질문",
        content="Markdown 본문입니다.",
        hashtags=["python", "fastapi"]
    )

    assert post.title == "Python 질문"
    assert len(post.hashtags) == 2

    expect_validation_error(
        PostCreateRequest,
        {"title": "", "content": "본문"}
    )

    update = PostUpdateRequest(
        hashtags=[],
        keep_image_ids=[]
    )

    data = update.model_dump(exclude_unset=True)

    assert data["hashtags"] == []
    assert data["keep_image_ids"] == []

    empty_update = PostUpdateRequest()
    assert "hashtags" not in empty_update.model_dump(
        exclude_unset=True
    )
    assert "keep_image_ids" not in empty_update.model_dump(
        exclude_unset=True
    )

    expect_validation_error(
        PostUpdateRequest,
        {"title": None}
    )


# -------------------------
# 5. 댓글 작성 및 수정
# -------------------------

def test_comment():
    comment = CommentCreateRequest(
        content="좋은 설명 감사합니다!"
    )
    assert comment.content == "좋은 설명 감사합니다!"

    expect_validation_error(
        CommentCreateRequest,
        {"content": ""}
    )

    expect_validation_error(
        CommentCreateRequest,
        {"content": "a" * 5001}
    )

    expect_validation_error(
        CommentUpdateRequest,
        {"content": None}
    )


# -------------------------
# 테스트 실행
# -------------------------

if __name__ == "__main__":
    run_test("회원가입 검증", test_auth)
    run_test("사용자 프로필 수정", test_user)
    run_test("태그 응답", test_tag)
    run_test("게시글 작성 및 수정", test_post)
    run_test("댓글 작성 및 수정", test_comment)
