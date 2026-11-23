
import pytest
import jwt

from app.core.security import (
    SECRET_KEY,
    ALGORITHM,
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)


def test_password():
    password = "password123"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong_password", hashed)

    print("[PASS] 비밀번호 해싱 및 검증")


def test_access_token():
    token = create_access_token(
        user_id=1,
        session_id=10,
    )

    payload = decode_token(
        token,
        expected_type="access",
    )

    assert payload["sub"] == "1"
    assert payload["sid"] == 10
    assert payload["type"] == "access"

    print("[PASS] Access Token 생성 및 검증")


def test_refresh_token():
    token = create_refresh_token(user_id=1)

    payload = decode_token(
        token,
        expected_type="refresh",
    )

    assert payload["sub"] == "1"
    assert payload["type"] == "refresh"
    assert "sid" not in payload

    token_hash = hash_refresh_token(token)

    assert len(token_hash) == 64
    assert token_hash != token
    assert token_hash == hash_refresh_token(token)

    print("[PASS] Refresh Token 생성 및 해싱")


def test_token_type():
    access_token = create_access_token(
        user_id=1,
        session_id=10,
    )

    with pytest.raises(ValueError):
        decode_token(
            access_token,
            expected_type="refresh",
        )

    print("[PASS] 토큰 유형 구분")


def test_missing_session_id():
    token = create_access_token(
        user_id=1,
        session_id=10,
    )

    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
    )

    # sid 제거 후 다시 서명
    payload.pop("sid")

    invalid_token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with pytest.raises(ValueError):
        decode_token(
            invalid_token,
            expected_type="access",
        )

    print("[PASS] 세션 ID 누락 검증")


@pytest.mark.parametrize(
    "invalid_sid",
    [0, -1, "10", True, None],
)
def test_invalid_session_id(invalid_sid):
    token = create_access_token(
        user_id=1,
        session_id=10,
    )

    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
    )

    # sid를 잘못된 값으로 변경 후 다시 서명
    payload["sid"] = invalid_sid

    invalid_token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with pytest.raises(ValueError):
        decode_token(
            invalid_token,
            expected_type="access",
        )

    print(f"[PASS] 잘못된 세션 ID 검증: {invalid_sid}")
