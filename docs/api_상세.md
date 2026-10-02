# API 상세

## Auth

### 1. POST `/auth/signup`

#### Request

- **설명** : 새로운 사용자 계정 생성 (회원가입)

- **Headers**
    - `Content-type`: application/json

- **Body**
    - raw
    ```json
    {
        "account_id": "testuser",
        "password": "securepassword"
    }
    ```

#### Response
- 정상 응답 시
```json
{
    "user_id": 1,
    "account_id": "testuser",
    "created_at": "2026-05-13T10:04:35.880059+09:00"
}
```

#### 비고
- 정상 응답 시 DB users 테이블에 해당 사용자 관련 row가 추가됨
- 이미 존재하는 사용자의 account_id와 동일한 account_id로 request를 전송할 경우 HTTPException 발생

### 2. POST `/auth/login`

- **설명** : 아이디와 비밀번호를 통해 로그인

#### Request

- **Headers**
    - `Content-type`: application/json

- **Body**
    - raw
    ```json
    {
        "account_id": "testuser",
        "password": "securepassword"
    }
    ```

#### Response

- 정상 응답 시
```json
{
    "access_token": "<access_token>",
    "refresh_token": "<refresh_token>",
    "token_type": "bearer",
    "user_id": 1,
    "account_id": "testuser"
}
```

#### 비고
- 로그인할 경우, access_token과 refresh_token을 발급받음. refresh_token은 `/auth/refresh`나 `/auth/logout`에서 사용됨
- account_id나 password를 올바르게 입력하지 않거나, 비활성화된 사용자 계정일 경우 HTTPException 발생


### 3. POST `/auth/logout`

- **설명** : refresh_token을 검증하여, DB 내 세션을 무효화하여 로그아웃 처리

#### Request

- **Headers**
    - `Content-type`: application/json

- **Body**
    - raw
    ```json
    {
        "refresh_token": "<refresh_token>"
    }
    ```

#### Response
- 정상 응답 시
```json
{
    "detail": "로그아웃이 완료되었습니다."
}
```

#### 비고
- 전달된 refresh_token이 유효하지 않거나 만료된 경우 HTTPException 발생


### 4. DELETE `/auth/withdraw`

- **설명**: Access Token 기반 회원 탈퇴.
    - 비밀번호 확인 후 Soft Delete (is_active=False 처리). 해당 사용자의 계정 비활성화시킴.
    - 해당 사용자의 모든 세션 무효화

#### Request

- **Headers**
    - `Content-type`: application/json
    - `Authorization`: bearer `<access_token>`

- **Body**
    - raw
    ```json
    {
        "password": "securepassword"
    }
    ```

#### Response
- 정상 응답 시
```json
{
    "detail": "회원 탈퇴가 완료되었습니다."
}
```

#### 비고
- 현재 로그인된 사용자의 올바른 password를 request로 전송하지 않으면 HTTPException 발생


### 5. POST `/auth/refresh`

- **설명** : refresh_token 기반 access_token 재발급

#### Request

- **Headers**
    - `Content-type`: application/json

- **Body**
    - raw
    ```json
    {
        "refresh_token": "<refresh_token>"
    }
    ```

#### Response
- 정상 응답 시
```json
{
    "access_token": "<new_access_token>",
    "refresh_token": "<refresh_token>",
    "token_type": "bearer"
}
```

#### 비고
- 정상 응답 시, 새 access_token을 발급받고, refresh_token은 기존의 것을 유지. DB sessions 테이블에 새 access_token에 대한 row가 추가됨.
- 기간이 만료되었거나, 현재 로그인한 사용자의 refresh_token과 일치하지 않은 refresh_token을 request로 전송할 경우 HTTPException 발생

## User

### 1. GET `/users/me`

- **설명** : 로그인한 사용자 자신의 프로필 조회

#### Request

- **Headers**
    - `Content-type` : application/json
    - `Authorization` : bearer `<access_token>`

#### Response
- 정상 응답 시
```json
{
    "id": 1,
    "account_id": "testuser",
    "username": "테스트 유저",
    "email": "testuser@example.com",
    "bio": "안녕하세요",
    "profile_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
    "is_active": true,
    "created_at": "2026-05-13T17:12:20.958165+09:00",
    "updated_at": "2026-05-13T17:13:30.514318+09:00"
}
```

#### 비고
- access_token이 만료되었거나 잘못된 경우 HTTPException 발생


### 2. PATCH `/users/me`

- **설명** : 자신의 프로필 정보 수정

#### Request

- **Headers**
    - `Content-Type` : multipart/form-data
    - `Authorization` : bearer `<access_token>`

- **Body**
    - form-data

    | key | type | example |
    |------|------|----------|
    | username | text | `새로운 닉네임` |
    | email | text | `testuser@newmail.com` |
    | bio | text | `변경된 자기소개` |
    | profile_image | file | `new_profile.jpg` |

    - 모든 필드는 **optional**

#### Response
- 정상 응답 시
```json
{
    "id": 1,
    "account_id": "testuser",
    "username": "새로운 닉네임",
    "email": "testuser@newmail.com",
    "bio": "변경된 자기소개",
    "profile_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
    "is_active": true,
    "created_at": "2026-05-13T17:12:20.958165+09:00",
    "updated_at": "2026-05-13T17:51:11.652801+09:00"
}
```

#### 비고
- access_token이 만료되었거나 잘못된 경우 HTTPException 발생
- 이미 존재하는 email을 request로 전송 시 HTTPException 발생


### 3. GET `/users/{user_id}`
- **설명** : 특정 사용자의 프로필 정보 조회

#### Request

- **Path Parameter**

| key | example |
| --- | ------- |
| user_id | 1 |

-> url 구조는 `/users/1`이 됨.

#### Response
- UserDetailResponse (정상 응답 시)
```json
{
    "id": 1,
    "account_id": "test123",
    "username": "테스트 유저",
    "email": "testuser@example.com",
    "bio": "안녕하세요",
    "profile_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
    "is_active": true,
    "created_at": "2025-11-13T17:12:20.958165+09:00",
    "updated_at": "2025-11-13T17:51:11.652801+09:00"
}
```

#### 비고
- 존재하지 않는 사용자일 경우 HTTPException 발생


### 4. GET `/users/{user_id}/posts`
- **설명** : 특정 사용자가 작성한 게시글 목록 조회

#### Request

- **Path Parameter**

| key | example |
| --- | ------- |
| user_id | 6 |

-> url 구조는 `/users/6/posts`가 됨.

#### Response

- PostDetailResponse[] (정상 응답 시)
```json
[
    {
        "id": 3,
        "title": "첫 게시글입니다.",
        "content": "이것은 첫 게시글",
        "image_urls": [
            "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/3417c0af-9d12-431e-9d5d-9bc71a088192.png",
            "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/bcd02cb4-3adf-41d9-a0d1-e90f11cb288b.png"
        ],
        "author_id": 6,
        "author_account_id": "test123",
        "author_username": "테스트 유저",
        "author_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
        "hashtags": [
            {
                "id": 1,
                "name": "Python"
            },
            {
                "id": 3,
                "name": "자료구조"
            }
        ],
        "like_count": 0,
        "comment_count": 0,
        "view_count": 0,
        "created_at": "2025-11-17T14:20:53.570229+09:00",
        "updated_at": "2025-11-17T14:20:53.570229+09:00",
        "is_blurred": false,
        "is_deleted": false,
        "report_count": 0
    },
    {
        "id": 2,
        "title": "첫 게시글입니다.",
        "content": "이것은 첫 게시글",
        "image_urls": [
            "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/9a1ee3a7-4a80-42d8-b740-f7e7c7ef0b14.png",
            "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/14ed90d3-ff3c-491f-9efb-2a1b15f69d7f.png"
        ],
        "author_id": 6,
        "author_account_id": "test123",
        "author_username": "테스트 유저",
        "author_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
        "like_count": 0,
        "comment_count": 0,
        "view_count": 1,
        "created_at": "2025-11-17T14:20:18.334643+09:00",
        "updated_at": "2025-11-17T14:21:30.012338+09:00",
        "is_blurred": false,
        "is_deleted": false,
        "report_count": 0
    }
]
```

#### 비고
- 사용자가 존재하지 않을 경우 HTTPException 발생
- 해당 사용자가 작성한 게시글이 없을 경우 빈 배열 `[]` 반환


### 5. GET `/users/{user_id}/likes/posts`
- **설명** : 특정 사용자가 좋아요한 게시글 목록 조회

#### Request

- **Path Parameter**

| key | example |
| --- | ------- |
| user_id | 6 |

-> url 구조는 `/users/6/likes/posts`가 됨.

#### Response

- PostDetailResponse[] (정상 응답 시)
```json
[
    {
        "id": 2,
        "title": "제목이 수정된 게시글",
        "content": "이 게시글은 수정되었습니다",
        "image_urls": [
            "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/7178fc98-bb48-4152-af4c-ff9e353cb8e4.png",
            "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/7a5885dd-9021-4ddd-9cd0-53fda46a323e.png"
        ],
        "author_id": 6,
        "author_account_id": "test123",
        "author_username": "testuser",
        "author_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
        "hashtags": [
            {
                "id": 4,
                "name": "수정된 태그"
            },
            {
                "id": 5,
                "name": "새로 추가된 태그"
            }
        ],
        "like_count": 1,
        "comment_count": 0,
        "view_count": 1,
        "created_at": "2025-11-17T14:20:18.334643+09:00",
        "updated_at": "2025-11-17T14:24:02.670078+09:00",
        "is_blurred": false,
        "is_deleted": false,
        "report_count": 0
    }
]
```

#### 비고
- 사용자가 존재하지 않을 경우 HTTPException 발생
- 좋아요한 게시글이 없으면 빈 배열 `[]` 반환


## Post

### 1. GET `/posts`
- **설명** : 게시글 조회. title(제목), tag(해시태그)로 필터링 가능

#### Request

- **Query Parameters**

| key | example |
| --- | ------- |
| title | 게시글 |
| tag | 수정된 태그 |

-> url 구조는 `/posts?title=게시글&tag=수정된 태그`가 됨.

#### Response

- PostDetailResponse[] (정상 응답 시)
```json
[
    {
        "id": 2,
        "title": "제목이 수정된 게시글",
        "content": "이 게시글은 수정되었습니다",
        "image_urls": [
            "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/7178fc98-bb48-4152-af4c-ff9e353cb8e4.png",
            "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/7a5885dd-9021-4ddd-9cd0-53fda46a323e.png"
        ],
        "author_id": 6,
        "author_account_id": "test123",
        "author_username": "testuser",
        "author_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
        "hashtags": [
            {
                "id": 4,
                "name": "수정된 태그"
            },
            {
                "id": 5,
                "name": "새로 추가된 태그"
            }
        ],
        "like_count": 1,
        "comment_count": 0,
        "view_count": 1,
        "created_at": "2025-11-17T14:20:18.334643+09:00",
        "updated_at": "2025-11-17T14:25:05.442793+09:00",
        "is_blurred": false,
        "is_deleted": false,
        "report_count": 0
    }
]
```

#### 비고
- 조회 필터를 만족하는 게시물이 없다면 빈 배열 `[]` 반환


### 2. POST `/posts`
- **설명** : 새 게시글 작성

#### Request

- **Headers**
    - `Content-Type` : multipart/form-data
    - `Authorization` : bearer `<access_token>`

- **Body** : PostCreate

    - form-data

    | key | type | example |
    |------|------|----------|
    | title | text | `첫 게시글입니다.` |
    | content | text | `이것은 첫 게시글` |
    | images  | file | [`image1.png`, `image2.png`] |
    | hashtags | text | [`Python`, `자료구조`] |

    - title, content는 필수 입력

#### Response

- PostDetailResponse (정상 응답 시)
```json
{
    "id": 3,
    "title": "첫 게시글입니다.",
    "content": "이것은 첫 게시글",
    "image_urls": [
        "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/3417c0af-9d12-431e-9d5d-9bc71a088192.png",
        "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/bcd02cb4-3adf-41d9-a0d1-e90f11cb288b.png"
    ],
    "author_id": 6,
    "author_account_id": "test123",
    "author_username": "testuser",
    "author_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
    "hashtags": [
        {
            "id": 1,
            "name": "Python"
        },
        {
            "id": 3,
            "name": "자료구조"
        }
    ],
    "like_count": 0,
    "comment_count": 0,
    "view_count": 0,
    "created_at": "2025-11-17T14:20:53.570229+09:00",
    "updated_at": "2025-11-17T14:20:53.570229+09:00",
    "is_blurred": false,
    "is_deleted": false,
    "report_count": 0
}
```

#### 비고
- 이미지 파일이 있을 경우 S3 스토리지에 업로드됨.


### 3. GET `/posts/{post_id}`
- **설명** : 게시글 상세 조회. 조회수 1 증가


#### Request

- **Path Parameter**

| key | example |
| --- | ------- |
| post_id | 2 |

-> url 구조는 `/posts/2`가 됨.

#### Response

- PostDetailResponse (정상 응답 시)
```json
{
    "id": 2,
    "title": "첫 게시글입니다.",
    "content": "이것은 첫 게시글",
    "image_urls": [
        "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/9a1ee3a7-4a80-42d8-b740-f7e7c7ef0b14.png",
        "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/14ed90d3-ff3c-491f-9efb-2a1b15f69d7f.png"
    ],
    "author_id": 6,
    "author_account_id": "test123",
    "author_username": "testuser",
    "author_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
    "hashtags": [
        {
            "id": 1,
            "name": "Python"
        },
        {
            "id": 2,
            "name": "자료구조"
        }
    ],
    "like_count": 0,
    "comment_count": 0,
    "view_count": 1,
    "created_at": "2025-11-17T14:20:18.334643+09:00",
    "updated_at": "2025-11-17T14:21:30.012338+09:00",
    "is_blurred": false,
    "is_deleted": false,
    "report_count": 0
}
```

#### 비고
- 존재하지 않는 게시글 조회 시 HTTPException 발생


### 4. PATCH `/posts/{post_id}`
- **설명** : 사용자 본인의 게시글 수정
    - 이미지, 해시태그 수정 가능

#### Request

- **Headers**
    - `Content-Type` : multipart/form-data
    - `Authorization` : bearer `<access_token>`

- **Path Parameter**

| key | example |
| --- | ------- |
| post_id | 2 |

-> url 구조는 `/posts/2`가 됨.

- **Body** : PostUpdate
    - form-data

    | key | type | example |
    |------|------|----------|
    | title | text | `제목이 수정된 게시글` |
    | content | text | `이 게시글은 수정되었습니다` |
    | images  | file | [`image3.png`, `image4.png`] |
    | hashtags | text | [`수정된 태그`, `새로 추가된 태그`] |

    - 모든 필드는 **optional**

#### Response
- PostDetailResponse (정상 응답 시)
```json
{
    "id": 2,
    "title": "제목이 수정된 게시글",
    "content": "이 게시글은 수정되었습니다",
    "image_urls": [
        "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/7178fc98-bb48-4152-af4c-ff9e353cb8e4.png",
        "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/posts/7a5885dd-9021-4ddd-9cd0-53fda46a323e.png"
    ],
    "author_id": 6,
    "author_account_id": "test123",
    "author_username": "testuser",
    "author_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
    "hashtags": [
        {
            "id": 4,
            "name": "수정된 태그"
        },
        {
            "id": 5,
            "name": "새로 추가된 태그"
        }
    ],
    "like_count": 0,
    "comment_count": 0,
    "view_count": 1,
    "created_at": "2025-11-17T14:20:18.334643+09:00",
    "updated_at": "2025-11-17T14:22:42.314093+09:00",
    "is_blurred": false,
    "is_deleted": false,
    "report_count": 0
}
```

#### 비고
- 제공된 필드만 업데이트됨.
- 사용자 본인이 작성하지 않은 게시글을 수정하려고 하면 HTTPException 발생


### 5. DELETE `/posts/{post_id}`
- **설명** : 본인 게시글 삭제

#### Request

- **Headers**
    - `Authorization` : bearer `<access_token>`

- **Path Parameter**

| key | example |
| --- | ------- |
| post_id | 3 |

-> url 구조는 `/posts/3`가 됨.

#### Response

- 정상 응답 시
```json
{
    "detail": "게시글이 삭제되었습니다."
}
```

#### 비고
- 본인이 작성하지 않은 게시글을 삭제 시도 시 HTTPException 발생
- 실제 게시글 삭제가 아닌, Soft Delete 방식(is_deleted=True 처리)


### 6. POST `/posts/{post_id}/likes`
- **설명** : 특정 게시글 좋아요 등록

#### Request

- **Headers**
    - `Authorization` : bearer `<access_token>`

- **Path Parameter**

| key | example |
| --- | ------- |
| post_id | 2 |

-> url 구조는 `/posts/2/likes`가 됨.

#### Response

- 정상 응답 시
```json
{
    "detail": "게시글 좋아요가 등록되었습니다."
}
```

#### 비고
- 이미 좋아요한 게시글에 대해 좋아요 등록 시도 시 HTTPException 발생
- 본인이 작성한 게시글에 대해 좋아요 등록도 가능


### 7. DELETE `/posts/{post_id}/likes`
- **설명** : 특정 게시글 좋아요 취소

#### Request

- **Headers**
    - `Authorization` : bearer `<access_token>`

- **Path Parameter**

| key | example |
| --- | ------- |
| post_id | 2 |

-> url 구조는 `/posts/2/likes`가 됨.

#### Response

- 정상 응답 시
```json
{
    "detail": "게시글 좋아요가 취소되었습니다."
}
```

#### 비고
- 좋아요 등록하지 않은 게시글을 좋아요 취소 시도할 경우 HTTPException 발생


## Comment

### 1. POST `/posts/{post_id}/comments`
- **설명** : 특정 게시글에 댓글 작성

#### Request

- **Headers**
    - `Content-Type` : application/json
    - `Authorization` : bearer `<access_token>`

- **Path Parameter**

| key | example |
| --- | ------- |
| post_id | 2 |

-> url 구조는 `/posts/2/comments`가 됨.

- **Body** : CommentCreate

    - raw
    ```json
    {
        "content" : "첫 번째 댓글입니다."
    }
    ```

#### Response

- CommentResponse (정상 응답 시)
```json
    {
        "id": 1,
        "post_id": 2,
        "user_id": 6,
        "username": "테스트 유저",
        "account_id": "test123",
        "profile_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
        "content": "첫 번째 댓글입니다.",
        "parent_comment_id": null,
        "created_at": "2025-11-18T00:40:34.820944+09:00",
        "updated_at": "2025-11-18T00:40:34.820944+09:00",
        "is_blurred": false,
        "is_deleted": false,
        "report_count": 0,
        "replies": []
    }
```

#### 비고
- 존재하지 않는 게시글에 댓글 작성하려 할 경우 HTTPException 발생


### 2. GET `/posts/{post_id}/comments`
- **설명** : 특정 게시글의 댓글 목록 조회
    - 응답에는 댓글, 대댓글이 모두 포함됨.

#### Request

- **Path Parameter**

| key | example |
| --- | ------- |
| post_id | 2 |

-> url 구조는 `/posts/2/comments`가 됨.

#### Response

- CommentResponse[] (정상 응답 시)
```json
[
    {
        "id": 1,
        "post_id": 2,
        "user_id": 6,
        "username": "테스트 유저",
        "account_id": "test123",
        "profile_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
        "content": "첫 번째 댓글입니다.",
        "parent_comment_id": null,
        "created_at": "2025-11-18T00:40:34.820944+09:00",
        "updated_at": "2025-11-18T00:40:34.820944+09:00",
        "is_blurred": false,
        "is_deleted": false,
        "report_count": 0,
        "replies": []
    },
    {
        "id": 2,
        "post_id": 2,
        "user_id": 6,
        "username": "테스트 유저",
        "account_id": "test123",
        "profile_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
        "content": "두 번째 댓글입니다.",
        "parent_comment_id": null,
        "created_at": "2025-11-18T00:40:46.395370+09:00",
        "updated_at": "2025-11-18T00:40:46.395370+09:00",
        "is_blurred": false,
        "is_deleted": false,
        "report_count": 0,
        "replies": []
    }
]
```

#### 비고
- 존재하지 않는 게시글에 대해 댓글 목록 조회 시 HTTPException 발생
- 댓글이 없으면 빈 배열 `[]` 반환


### 3. PATCH `/posts/{post_id}/comments/{comment_id}`
- **설명** : 댓글 내용 수정 (댓글 작성자 본인만 가능)

#### Request

- **Headers**
    - `Content-Type` : application/json
    - `Authorization` : bearer `<access_token>`

- **Path Parameter**

| key | example |
| --- | ------- |
| post_id | 2 |
| comment_id | 1 |

-> url 구조는 `/api/posts/2/comments/1`가 됨.

- **Body** : CommentUpdate

    - raw
    ```json
    {
        "content" : "이 댓글은 수정되었습니다."
    }
    ```

#### Response

- CommentResponse (정상 응답 시)
```json
{
    "id": 1,
    "post_id": 2,
    "user_id": 6,
    "username": "testuser",
    "account_id": "테스트 유저",
    "profile_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
    "content": "이 댓글은 수정되었습니다.",
    "parent_comment_id": null,
    "created_at": "2025-11-18T00:40:34.820944+09:00",
    "updated_at": "2025-11-18T00:41:22.045239+09:00",
    "is_blurred": false,
    "is_deleted": false,
    "report_count": 0,
    "replies": []
}
```

#### 비고
- 사용자 본인이 작성하지 않은 댓글을 수정하려 시도할 경우 HTTPException 발생
- 존재하지 않는 댓글을 수정하려 시도할 경우 HTTPException 발생


### 4. DELETE `/posts/{post_id}/comments/{comment_id}`
- **설명** : 특정 댓글 삭제 (작성자 본인만 가능)
    - 삭제하려는 댓글에 대댓글이 존재한다면, 대댓글까지 삭제

#### Request

- **Headers**
    - `Content-Type` : application/json
    - `Authorization` : bearer `<access_token>`

- **Path Parameter**

| key | example |
| --- | ------- |
| post_id | 2 |
| comment_id | 2 |

-> url 구조는 `/posts/2/comments/2`가 됨.

#### Response

- 정상 응답 시
```json
{
    "detail": "댓글이 삭제되었습니다."
}
```

#### 비고
- 본인이 작성하지 않은 댓글을 삭제 시도 시 HTTPException 발생
- 실제 댓글 삭제가 아닌, Soft Delete 방식(is_deleted=True 처리). 대댓글도 Soft Delete 방식으로 처리함.
    - post의 comment_count는 삭제하는 댓글, 대댓글 수만큼 감소함.


### 5. POST `/posts/{post_id}/comments/{comment_id}/replies`
- **설명** : 특정 댓글에 대댓글 작성

#### Request

- **Headers**
    - `Content-Type` : application/json
    - `Authorization` : bearer `<access_token>`

- **Path Parameter**

| key | example |
| --- | ------- |
| post_id | 2 |
| comment_id | 2 |

-> url 구조는 `/posts/2/comments/2/replies`가 됨.

- **Body** : CommentCreate

    - raw
    ```json
    {
        "content" : "이것은 대댓글입니다."
    }
    ```

#### Response

- CommentResponse (정상 응답 시)
```json
{
    "id": 4,
    "post_id": 2,
    "user_id": 6,
    "username": "testuser",
    "account_id": "test123",
    "profile_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
    "content": "이것은 대댓글입니다.",
    "parent_comment_id": 2,
    "created_at": "2025-11-18T00:41:55.251528+09:00",
    "updated_at": "2025-11-18T00:41:55.251528+09:00",
    "is_blurred": false,
    "is_deleted": false,
    "report_count": 0,
    "replies": []
}
```

#### 비고
- 존재하지 않는 댓글에 대댓글 작성하려 할 경우 HTTPException 발생