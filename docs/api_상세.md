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
- 정상 응답 시, 새 access_token을 발급받고, refresh_token은 기존의 것을 유지. DB sessions 테이블에 새 access_token에 대한 row가 추가됨. (제외 예정?)
- 정상 응답 시 새로운 Access Token을 발급하고 기존 Refresh Token 및 세션은 유지한다. 새로운 sessions row는 생성하지 않는다.
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
        "is_deleted": false
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
        "updated_at": "2025-11-17T14:21:30.012338+09:00",
        "is_deleted": false
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
        "is_deleted": false
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
        "is_deleted": false
    }
]
```

#### 비고
- 조회 필터를 만족하는 게시물이 없다면 빈 배열 `[]` 반환


### 2. POST `/posts`

- **설명** : 새 게시글 작성
    - 게시글 본문은 Markdown 형식으로 저장
    - 본문에 이미지 삽입 가능
    - 이미지 파일과 임시 이미지 ID를 연결하여 S3에 업로드

#### Request

- **Headers**
    - `Content-Type` : multipart/form-data
    - `Authorization` : bearer `<access_token>`

- **Body** : PostCreate
    - form-data

    | key | type | example |
    |------|------|----------|
    | title | text | `Python 공부 기록` |
    | content | text | `Python으로 그래프를 만들었습니다.\n\n![그래프](upload://graph_abc)\n\n실행 결과입니다.\n\n![실행 결과](upload://result_xyz)` |
    | images | file | `graph.png`, `result.png` |
    | image_ids | text | `graph_abc`, `result_xyz` |
    | hashtags | text | `Python`, `Matplotlib` |

    - `title`, `content`는 필수 입력
    - `images`, `image_ids`, `hashtags`는 선택 입력
    - `images`, `image_ids`, `hashtags`는 동일한 key를 반복하여 여러 값을 전달할 수 있음
    - `images`와 `image_ids`는 같은 순서로 전달해야 함
    - 이미지 파일 하나당 하나의 `image_id`가 필요함

- **content 예시**

    ```markdown
    Python으로 그래프를 만들었습니다.

    ![그래프](upload://graph_abc)

    실행 결과입니다.

    ![실행 결과](upload://result_xyz)
    ```

- **이미지 매칭 예시**

    | image_ids | images |
    |-----------|--------|
    | `graph_abc` | `graph.png` |
    | `result_xyz` | `result.png` |

#### Response

- PostDetailResponse (정상 응답 시)

```json
{
    "id": 3,
    "title": "Python 공부 기록",
    "content": "Python으로 그래프를 만들었습니다.\n\n![그래프](https://example.com/posts/graph.png)\n\n실행 결과입니다.\n\n![실행 결과](https://example.com/posts/result.png)",
    "image_urls": [
        "https://example.com/posts/graph.png",
        "https://example.com/posts/result.png"
    ],
    "author_id": 6,
    "author_account_id": "test123",
    "author_username": "테스트 유저",
    "author_image_url": null,
    "hashtags": [
        {
            "id": 1,
            "name": "Python"
        },
        {
            "id": 2,
            "name": "Matplotlib"
        }
    ],
    "like_count": 0,
    "comment_count": 0,
    "view_count": 0,
    "created_at": "2026-10-31T14:20:53+09:00",
    "updated_at": "2026-10-31T14:20:53+09:00",
    "is_deleted": false
}
```

#### 비고

- 이미지 파일은 S3 스토리지에 업로드됨.
- 서버는 `image_ids`와 `images`를 같은 순서로 연결하여 이미지 파일을 식별함.
- `content` 내의 `upload://{image_id}` 참조를 S3 업로드 후 실제 이미지 URL로 치환하여 DB에 저장함.
- 이미지가 없는 게시글은 `images`, `image_ids`를 생략할 수 있으며, `image_urls`는 빈 배열 `[]`로 반환됨.
- 이미지 파일이 있는 경우 `images`와 `image_ids`의 개수가 일치해야 함.
- 하나의 요청에서 `image_ids` 값은 중복될 수 없음.
- 업로드된 이미지 파일은 `content` 내에서 최소 한 번 이상 참조되어야 함.
- `content`에 존재하는 임시 이미지 ID에 대응하는 파일이 없는 경우 HTTPException 발생.
- 이미지 업로드 또는 게시글 저장 중 오류가 발생하면 요청을 실패 처리하며, 업로드 완료 후 저장에 실패한 S3 객체는 정리하도록 구현함.


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
    "is_deleted": false
}
```

#### 비고
- 존재하지 않는 게시글 조회 시 HTTPException 발생


### 4. PATCH `/posts/{post_id}`

- **설명** : 사용자 본인의 게시글 수정
    - 제목, Markdown 본문, 이미지, 해시태그 수정 가능
    - 기존 이미지를 유지하면서 새 이미지를 추가하거나 기존 이미지를 제거할 수 있음
    - 해시태그는 전달된 목록으로 전체 교체

#### Request

- **Headers**
    - `Content-Type` : multipart/form-data
    - `Authorization` : bearer `<access_token>`

- **Path Parameter**

    | key | example |
    |-----|---------|
    | post_id | 2 |

    → URL 구조는 `/posts/2`가 됨.

- **Body** : PostUpdate
    - form-data

    | key | type | example |
    |------|------|----------|
    | title | text | `수정된 Python 공부 기록` |
    | content | text | `기존 그래프입니다.\n\n![기존 이미지](https://example.com/posts/old.png)\n\n새로운 결과입니다.\n\n![새 이미지](upload://new_xyz)` |
    | images | file | `new_result.png` |
    | image_ids | text | `new_xyz` |
    | hashtags | text | `Python`, `시각화` |

    - 모든 필드는 선택 입력
    - `images`, `image_ids`, `hashtags`는 동일한 key를 반복하여 여러 값을 전달할 수 있음
    - `images`와 `image_ids`는 같은 순서로 전달해야 함
    - 새 이미지 파일 하나당 하나의 `image_id`가 필요함

- **content 수정 예시**

    기존 게시글의 `content`:

    ```markdown
    기존 그래프입니다.

    ![기존 이미지](https://example.com/posts/old.png)

    더 이상 필요하지 않은 이미지입니다.

    ![삭제할 이미지](https://example.com/posts/remove.png)
    ```

    수정 요청의 `content`:

    ```markdown
    기존 그래프입니다.

    ![기존 이미지](https://example.com/posts/old.png)

    새로운 결과입니다.

    ![새 이미지](upload://new_xyz)
    ```

    위 요청에서는 다음과 같이 처리됨.

    - `old.png` : 기존 이미지 유지
    - `remove.png` : 본문에서 참조가 제거되었으므로 게시글 이미지 목록에서 제거
    - `new_result.png` : S3에 업로드한 뒤 `upload://new_xyz`를 실제 이미지 URL로 치환

#### Response

- PostDetailResponse (정상 응답 시)

```json
{
    "id": 2,
    "title": "수정된 Python 공부 기록",
    "content": "기존 그래프입니다.\n\n![기존 이미지](https://example.com/posts/old.png)\n\n새로운 결과입니다.\n\n![새 이미지](https://example.com/posts/new_result.png)",
    "image_urls": [
        "https://example.com/posts/old.png",
        "https://example.com/posts/new_result.png"
    ],
    "author_id": 6,
    "author_account_id": "test123",
    "author_username": "테스트 유저",
    "author_image_url": null,
    "hashtags": [
        {
            "id": 1,
            "name": "Python"
        },
        {
            "id": 4,
            "name": "시각화"
        }
    ],
    "like_count": 1,
    "comment_count": 0,
    "view_count": 1,
    "created_at": "2026-10-30T14:20:18+09:00",
    "updated_at": "2026-10-31T14:22:42+09:00",
    "is_deleted": false
}
```

#### 비고

- 사용자 본인이 작성하지 않은 게시글을 수정하려고 하면 HTTPException 발생.
- 제공된 필드만 수정하며, 전달하지 않은 필드는 기존 값을 유지함.
- `content`가 전달되지 않으면 기존 본문과 이미지 구성을 유지함.
- 새 이미지 추가 또는 기존 이미지 제거를 위해서는 수정된 `content`를 함께 전달해야 함.
- `content`가 전달되면 해당 Markdown에 포함된 기존 이미지 URL을 기준으로 유지할 이미지를 판단함.
- 본문에서 참조가 제거된 기존 이미지는 `PostImage`의 연결 정보에서 제거함. S3 객체의 실제 삭제 여부와 시점은 별도 저장소 정리 정책에 따름.
- 기존 게시글에 속하지 않는 이미지 URL을 기존 이미지로 참조하려는 경우 HTTPException 발생.
- 새 이미지를 첨부하는 경우 `images`, `image_ids`를 함께 전달해야 하며, 두 필드의 개수가 일치해야 함.
- 새 이미지의 임시 ID는 중복될 수 없으며, `content`에서 참조되어야 함.
- `content`에 존재하는 임시 이미지 ID에 대응하는 파일이 없으면 HTTPException 발생.
- `hashtags`를 전달하면 기존 해시태그 연결을 해제하고 전달된 해시태그 목록으로 전체 교체함.
- `hashtags`를 전달하지 않으면 기존 해시태그를 유지함.
- 해시태그를 모두 제거하려면 별도로 정의한 빈 목록 전달 규칙을 사용해야 함.
- 삭제된 게시글은 수정할 수 없음.



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
        "is_deleted": false,
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
        "is_deleted": false,
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
        "is_deleted": false,
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

-> url 구조는 `/posts/2/comments/1`가 됨.

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
    "username": "테스트 유저",
    "account_id": "test123",
    "profile_image_url": "https://fish-market-files.s3.ap-northeast-2.amazonaws.com/profile-images/b7d20faa-726c-4c89-8848-5a505cd41bd7.jpg",
    "content": "이 댓글은 수정되었습니다.",
    "parent_comment_id": null,
    "created_at": "2025-11-18T00:40:34.820944+09:00",
    "updated_at": "2025-11-18T00:41:22.045239+09:00",
    "is_deleted": false,
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
    "is_deleted": false,
    "replies": []
}
```

#### 비고
- 존재하지 않는 댓글에 대댓글 작성하려 할 경우 HTTPException 발생
- 대댓글은 최상위 댓글에 대해서만 작성 가능
- 대댓글에 다시 대댓글 작성 불가
- 삭제된 댓글에는 대댓글 작성 불가