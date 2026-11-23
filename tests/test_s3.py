
from io import BytesIO

import pytest
import requests
from fastapi import UploadFile
from PIL import Image
from starlette.datastructures import Headers

from app.services.s3 import (
    MAX_IMAGE_SIZE,
    ImageValidationError,
    validate_image,
    validate_object_key,
    upload_image,
    generate_image_url,
    delete_image,
)


# -------------------------
# 테스트 이미지 생성
# -------------------------

def create_test_image() -> bytes:
    image = Image.new(
        "RGB",
        (10, 10),
        color="blue",
    )

    buffer = BytesIO()
    image.save(buffer, format="JPEG")

    return buffer.getvalue()


# -------------------------
# 이미지 검증 테스트
# -------------------------

def test_validate_image_success():
    content = create_test_image()

    content_type, extension = validate_image(
        content,
        "image/jpeg",
    )

    assert content_type == "image/jpeg"
    assert extension == "jpg"


def test_validate_empty_image():
    with pytest.raises(ImageValidationError):
        validate_image(
            b"",
            "image/jpeg",
        )


def test_validate_oversized_image():
    content = b"a" * (MAX_IMAGE_SIZE + 1)

    with pytest.raises(ImageValidationError):
        validate_image(
            content,
            "image/jpeg",
        )


def test_validate_content_type_mismatch():
    content = create_test_image()

    with pytest.raises(ImageValidationError):
        validate_image(
            content,
            "image/png",
        )


def test_validate_invalid_object_key():
    invalid_keys = [
        "",
        "invalid/test.jpg",
        "profiles/",
        "profiles/../test.jpg",
        "posts//test.jpg",
    ]

    for key in invalid_keys:
        with pytest.raises(ImageValidationError):
            validate_object_key(key)


# -------------------------
# 실제 S3 연동 테스트
# -------------------------

@pytest.mark.integration
def test_s3_image_lifecycle():
    content = create_test_image()

    file = UploadFile(
        filename="test.jpg",
        file=BytesIO(content),
        headers=Headers({
            "content-type": "image/jpeg",
        }),
    )

    object_key = None

    try:
        # 1. 이미지 업로드
        object_key = upload_image(
            file=file,
            folder="profiles",
            owner_id=1,
        )

        assert object_key.startswith("profiles/1/")
        assert object_key.endswith(".jpg")

        # 2. Presigned URL 생성
        image_url = generate_image_url(object_key)

        assert image_url.startswith("https://")

        # 3. 실제 이미지 조회
        response = requests.get(
            image_url,
            timeout=10,
        )

        if response.status_code != 200:
            print("S3 HTTP 상태 코드:", response.status_code)
            print("S3 오류 응답:", response.text)
        
        assert response.status_code == 200
        assert response.content == content

    finally:
        # 4. 테스트 이미지 삭제
        if object_key is not None:
            delete_image(object_key)

        file.file.close()
