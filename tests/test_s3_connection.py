import os
from io import BytesIO

import boto3
from dotenv import load_dotenv


# .env 로드
load_dotenv()

# AWS 설정
AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")

# S3 클라이언트 생성
s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
)


def test_s3_connection():
    # 1. 테스트 파일 생성
    test_content = b"Agent-CS S3 connection test"

    test_key = "profiles/test_connection.txt"

    # 2. S3에 업로드
    s3.upload_fileobj(
        BytesIO(test_content),
        AWS_S3_BUCKET_NAME,
        test_key,
    )

    # 3. 업로드한 파일 조회
    response = s3.get_object(
        Bucket=AWS_S3_BUCKET_NAME,
        Key=test_key,
    )

    downloaded_content = response["Body"].read()

    # 4. 파일 내용 검증
    assert downloaded_content == test_content

    # 5. 테스트 파일 삭제
    s3.delete_object(
        Bucket=AWS_S3_BUCKET_NAME,
        Key=test_key,
    )

    print("S3 업로드, 조회, 삭제 테스트 성공")