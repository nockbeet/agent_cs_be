
import os
from io import BytesIO
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from botocore.config import Config


# 환경변수 로드
load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")

# 이미지 업로드 정책
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MiB

ALLOWED_IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
    "GIF": ("image/gif", "gif"),
}

ALLOWED_PREFIXES = {"profiles", "posts"}

PRESIGNED_URL_EXPIRES = 3600  # 1시간


class S3ImageError(Exception):
    """S3 이미지 처리 오류"""


class ImageValidationError(S3ImageError):
    """이미지 파일 검증 오류"""


class ImageStorageError(S3ImageError):
    """S3 저장소 작업 오류"""


def get_s3_client():
    """AWS S3 클라이언트 생성"""
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        endpoint_url=f"https://s3.{AWS_REGION}.amazonaws.com",
        config=Config(
            signature_version="s3v4",
            s3={
                "addressing_style": "virtual",
            },
        ),
    )


def validate_image(
    file_content: bytes,
    content_type: str | None,
) -> tuple[str, str]:
    """
    이미지 파일 검증

    반환값:
        (MIME 타입, 확장자)
    """

    if not file_content:
        raise ImageValidationError(
            "빈 파일은 업로드할 수 없습니다."
        )

    if len(file_content) > MAX_IMAGE_SIZE:
        raise ImageValidationError(
            "이미지 크기는 5MB를 초과할 수 없습니다."
        )

    try:
        # 이미지 헤더 및 파일 구조 검증
        with Image.open(BytesIO(file_content)) as image:
            image_format = image.format
            image.verify()

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
    ) as exc:
        raise ImageValidationError(
            "올바른 이미지 파일이 아닙니다."
        ) from exc

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ImageValidationError(
            "지원하지 않는 이미지 형식입니다."
        )

    expected_type, extension = ALLOWED_IMAGE_FORMATS[
        image_format
    ]

    if content_type != expected_type:
        raise ImageValidationError(
            "이미지 파일 형식과 Content-Type이 일치하지 않습니다."
        )

    return expected_type, extension


def validate_object_key(object_key: str) -> None:
    """허용된 S3 객체 경로인지 확인"""

    if not object_key or "/" not in object_key:
        raise ImageValidationError(
            "올바르지 않은 이미지 경로입니다."
        )

    prefix, remainder = object_key.split("/", 1)

    if (
        prefix not in ALLOWED_PREFIXES
        or not remainder
        or any(
            segment in {"", ".", ".."}
            for segment in remainder.split("/")
        )
    ):
        raise ImageValidationError(
            "허용되지 않은 이미지 경로입니다."
        )


def upload_image(
    file: UploadFile,
    folder: str,
    owner_id: int,
) -> str:
    """
    이미지 업로드

    반환값:
        S3 객체 키
    """

    if folder not in ALLOWED_PREFIXES:
        raise ImageValidationError(
            "허용되지 않은 이미지 저장 경로입니다."
        )

    if owner_id <= 0:
        raise ImageValidationError(
            "올바르지 않은 사용자 또는 게시글 ID입니다."
        )

    # 파일 크기 제한을 초과하는지 먼저 확인
    file_content = file.file.read(MAX_IMAGE_SIZE + 1)

    content_type, extension = validate_image(
        file_content,
        file.content_type,
    )

    # 고유한 객체 키 생성
    object_key = (
        f"{folder}/{owner_id}/{uuid4().hex}.{extension}"
    )

    try:
        get_s3_client().put_object(
            Bucket=AWS_S3_BUCKET_NAME,
            Key=object_key,
            Body=file_content,
            ContentType=content_type,
        )

    except (BotoCoreError, ClientError) as exc:
        raise ImageStorageError(
            "이미지 업로드에 실패했습니다."
        ) from exc

    return object_key


def generate_image_url(object_key: str) -> str:
    """
    비공개 이미지 조회용 Presigned URL 생성
    """

    validate_object_key(object_key)

    try:
        return get_s3_client().generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": AWS_S3_BUCKET_NAME,
                "Key": object_key,
            },
            ExpiresIn=PRESIGNED_URL_EXPIRES,
        )

    except (BotoCoreError, ClientError) as exc:
        raise ImageStorageError(
            "이미지 조회 URL 생성에 실패했습니다."
        ) from exc


def delete_image(object_key: str) -> None:
    """
    S3 이미지 삭제
    """

    validate_object_key(object_key)

    try:
        get_s3_client().delete_object(
            Bucket=AWS_S3_BUCKET_NAME,
            Key=object_key,
        )

    except (BotoCoreError, ClientError) as exc:
        raise ImageStorageError(
            "이미지 삭제에 실패했습니다."
        ) from exc
