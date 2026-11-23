# API 상세

> Agent-CS API 문서. 아래 URL·응답 필드·검증 규칙은 공유된 FastAPI 라우터 및 Pydantic 스키마를 기준으로 정리했다. 예시의 날짜, ID, Presigned URL은 설명용이며 실제 응답과 달라질 수 있다.

## Auth

### 1. POST `/auth/signup`

- **설명**: 새로운 사용자 계정 생성 (회원가입)

#### Request

- **Headers**: `Content-Type: application/json`
- **Body** — `SignupRequest`

```json
{
  "account_id":"testuser",
  "password":"securepassword"
}
```

| 필드 | 타입 | 조건 |
| --- | --- | --- |
| `account_id` | string | 필수, 4~30자, 영문 소문자·숫자·밑줄(`_`)만 허용 |
| `password` | string | 필수, 8~128자 |

#### Response

- **201 Created** — `SignupResponse`

```json
{
  "user_id":1,
  "account_id":"testuser",
  "created_at":"2026-11-23T10:04:35+09:00"
}
```

#### 비고

- `users` 테이블에 사용자 레코드가 생성되며 비밀번호는 해시값으로 저장됨.
- `account_id` 중복 시 **409 Conflict**.
- 입력 조건 위반 또는 비밀번호 해시 처리 검증 오류 시 **422 Unprocessable Entity**.
- 회원가입만으로 토큰은 발급되지 않음.

### 2. POST `/auth/login`

- **설명**: 계정 ID와 비밀번호로 로그인하고 Access/Refresh Token 발급

#### Request

- **Headers**: `Content-Type: application/json`
- **Body** — `LoginRequest`

```json
{
  "account_id":"testuser",
  "password":"securepassword"
}
```

#### Response

- **200 OK** — `LoginResponse`

```json
{
  "access_token":"<access_token>","refresh_token":"<refresh_token>",
  "token_type":"bearer",
  "user_id":1,
  "account_id":"testuser"
}
```

#### 비고

- 계정 ID/비밀번호 오류 또는 비활성 계정이면 **401 Unauthorized**.
- **단일 세션 정책**: 로그인할 때 기존 유효 세션을 `is_valid=False`로 무효화하고 새 세션을 생성함. 이전 세션 레코드는 유지함.
- Refresh Token 해시를 DB에 저장하고, Access Token에 사용자 ID와 세션 ID를 포함함.
- Refresh Token은 `/auth/refresh`, `/auth/logout`에서 사용함.

### 3. POST `/auth/logout`

- **설명**: Refresh Token에 연결된 세션 무효화

#### Request

- **Headers**: `Content-Type: application/json`
- **Body** — `LogoutRequest`

```json
{
  "refresh_token":"<refresh_token>"
}
```

#### Response

- **200 OK** — `MessageResponse`

```json
{
  "message":"로그아웃되었습니다."
}
```

#### 비고

- Access Token Authorization 헤더는 필요하지 않으며, 본문의 Refresh Token을 검증함.
- 토큰 종류·서명·만료 및 DB의 세션 유효성·소유자를 확인함.
- 정상 처리 시 해당 세션의 `is_valid=False`.
- 잘못되거나 만료된 토큰, 무효화된 세션은 인증 오류가 발생함.

### 4. DELETE `/auth/withdraw`

- **설명**: 비밀번호를 재확인하고 회원 탈퇴 (Soft Delete)

#### Request

- **Headers**: `Content-Type: application/json`, `Authorization: Bearer <access_token>`
- **Body** — `WithdrawRequest`

```json
{
  "password":"securepassword"
}
```

#### Response

- **200 OK** — `MessageResponse`

```json
{
  "message":"회원 탈퇴가 완료되었습니다."
}
```

#### 비고

- Access Token 인증이 필요함.
- 비밀번호가 일치하지 않으면 **401 Unauthorized**.
- `users.is_active=False`, `updated_at` 갱신 및 해당 사용자의 모든 유효 세션 무효화.
- 사용자 레코드는 물리적으로 삭제하지 않으며 비활성 계정은 로그인할 수 없음.

### 5. POST `/auth/refresh`

- **설명**: Refresh Token을 사용해 새 Access Token 발급

#### Request

- **Headers**: `Content-Type: application/json`
- **Body** — `RefreshRequest`

```json
{
  "refresh_token":"<refresh_token>"
}
```

#### Response

- **200 OK** — `RefreshResponse`

```json
{
  "access_token":"<new_access_token>",
  "token_type":"bearer"
}
```

#### 비고

- Access Token Authorization 헤더는 필요하지 않음.
- Refresh Token, DB 세션 및 사용자 활성 상태를 검증함.
- 기존 세션 ID로 Access Token만 새로 발급하며 **Refresh Token을 재발급하지 않고 새 세션도 만들지 않음**.
- 잘못되거나 만료된 Refresh Token, 무효 세션, 비활성 계정은 인증 오류가 발생함.

## User

### 1. GET `/users/me`

- **설명**: 로그인한 사용자 자신의 프로필 조회

#### Request

- **Headers**: `Authorization: Bearer <access_token>`

#### Response

- **200 OK** — `UserDetailResponse`

```json
{
  "id":1,
  "account_id":"testuser",
  "username":"테스트 유저",
  "email":"testuser@example.com",
  "bio":"안녕하세요",
  "profile_image_url":"https://example.com/profiles/profile.jpg?signature=example",
  "is_active":true,
  "created_at":"2026-11-20T17:12:20+09:00",
  "updated_at":"2026-11-20T17:13:30+09:00"
}
```

#### 비고

- Access Token 인증 필요.
- 프로필 이미지가 존재하면 S3 객체 키로 Presigned URL을 생성하며, 없으면 `profile_image_url=null`.
- 이미지 URL 생성 실패 시 **502 Bad Gateway**; 토큰이 유효하지 않으면 인증 오류.

### 2. PATCH `/users/me`

- **설명**: 자신의 프로필 수정. 전달하지 않은 필드는 기존 값 유지.

#### Request

- **Headers**: `Content-Type: multipart/form-data`, `Authorization: Bearer <access_token>`
- **Body** — form-data

| key | type | example | 조건 |
| --- | --- | --- | --- |
| `username` | text | `새로운 닉네임` | 선택, 1~30자 |
| `email` | text | `testuser@newmail.com` | 선택, 이메일 형식 |
| `bio` | text | `변경된 자기소개` | 선택, 최대 500자 |
| `profile_image` | file | `new_profile.jpg` | 선택, 이미지 파일 |

#### Response

- **200 OK** — `UserDetailResponse`

```json
{
  "id":1,
  "account_id":"testuser",
  "username":"새로운 닉네임",
  "email":"testuser@newmail.com",
  "bio":"변경된 자기소개",
  "profile_image_url":"https://example.com/profiles/new_profile.jpg?signature=example",
  "is_active":true,
  "created_at":"2026-11-20T17:12:20+09:00",
  "updated_at":"2026-11-23T17:51:11+09:00"
}
```

#### 비고

- `username`은 빈 문자열 및 문자열 `"null"` 불가. `email`도 문자열 `"null"` 불가. 입력 검증 실패 시 **422**.
- `bio`에 정확히 문자열 `"null"`을 전달하면 자기소개를 `None`으로 변경함. `"NULL"`은 해당하지 않음.
- 다른 사용자가 이미 사용 중인 이메일이면 **409 Conflict**.
- 새 프로필 이미지는 S3의 `profiles` 폴더에 업로드하고 객체 키를 DB에 저장함.
- DB 저장 성공 후 기존 이미지 삭제를 시도하며, 기존 이미지 삭제 실패는 완료된 요청을 취소하지 않음.
- DB 저장 실패 시 새로 업로드한 S3 객체 삭제를 시도함.
- 이미지 검증 실패 **400**, S3 업로드 또는 URL 생성 실패 **502**, DB 충돌 **409**, 기타 DB 저장 오류 **500**.
- 기존 이미지만 단독 제거하는 별도 입력 규칙은 구현되어 있지 않음.

### 3. GET `/users/{user_id}`

- **설명**: 특정 사용자의 프로필 조회

#### Request

| Path Parameter | type | example |
| --- | --- | --- |
| `user_id` | integer | `1` |

- URL 예시: `/users/1`

#### Response

- **200 OK** — `UserDetailResponse`

```json
{
  "id":1,
  "account_id":"testuser",
  "username":"테스트 유저",
  "email":"testuser@example.com",
  "bio":"안녕하세요",
  "profile_image_url":null,
  "is_active":true,
  "created_at":"2026-11-20T17:12:20+09:00",
  "updated_at":"2026-11-20T17:51:11+09:00"
}
```

#### 비고

- 인증 없이 조회 가능.
- 존재하지 않거나 비활성화된 사용자는 **404 Not Found**.
- 프로필 이미지가 있으면 Presigned URL을 생성하며 없으면 `null`.

### 4. GET `/users/{user_id}/posts`

- **설명**: 특정 사용자가 작성한 게시글 목록 조회

#### Request

| Path Parameter | type | example |
| --- | --- | --- |
| `user_id` | integer | `6` |

- URL 예시: `/users/6/posts`

#### Response

- **200 OK** — `PostListResponse[]`

```json
[
  {
    "id":3,
    "title":"Python 공부 기록",
    "author_id":6,
    "author_account_id":"test123",
    "author_username":"테스트 유저",
    "author_image_url":null,
    "hashtags":[
      {
        "id":1,
        "name":"python"
      },
      {"id":2,
      "name":"자료구조"
      }
    ],
    "like_count":2,
    "comment_count":3,
    "view_count":10,
    "created_at":"2026-11-21T14:20:53+09:00",
    "updated_at":"2026-11-21T14:20:53+09:00"
  },
  {
    "id":2,
    "title":"알고리즘 정리",
    "author_id":6,
    "author_account_id":"test123",
    "author_username":"테스트 유저",
    "author_image_url":null,
    "hashtags":[
      {
        "id":3,
        "name":"알고리즘"
      }
    ],
    "like_count":0,
    "comment_count":1,
    "view_count":5,
    "created_at":"2026-11-20T14:20:18+09:00",
    "updated_at":"2026-11-20T14:21:30+09:00"
  }
]
```

#### 비고

- 인증 없이 조회 가능. 존재하지 않거나 비활성화된 사용자면 **404**.
- `is_deleted=False`인 게시글만 반환하며 `created_at DESC`, `id DESC` 정렬.
- 게시글이 없으면 `[]`; 별도 페이지네이션 파라미터는 없음.
- 목록 응답에 `content`, `images`, `is_deleted`는 포함되지 않음.
- 작성자 이미지가 있으면 `author_image_url`에 Presigned URL을 반환함.

### 5. GET `/users/{user_id}/likes/posts`

- **설명**: 특정 사용자가 좋아요한 게시글 목록 조회

#### Request

| Path Parameter | type | example |
| --- | --- | --- |
| `user_id` | integer | `6` |

- URL 예시: `/users/6/likes/posts`

#### Response

- **200 OK** — `PostListResponse[]`

```json
[
  {
    "id":2,
    "title":"알고리즘 정리",
    "author_id":8,
    "author_account_id":"anotheruser",
    "author_username":"다른 사용자",
    "author_image_url":null,
    "hashtags":[
      {
        "id":3,
        "name":"알고리즘"
      }
    ],
    "like_count":5,
    "comment_count":2,
    "view_count":20,
    "created_at":"2026-11-20T14:20:18+09:00",
    "updated_at":"2026-11-22T14:24:02+09:00"
  }
]
```

#### 비고

- 인증 없이 조회 가능. 존재하지 않거나 비활성화된 사용자면 **404**.
- 좋아요한 게시글 중 `is_deleted=False`인 게시글만 반환.
- `created_at DESC`, `id DESC` 정렬. 없으면 `[]`.
- `PostListResponse[]` 형식으로 `content`, `images`, `is_deleted` 필드는 포함되지 않음.
- 조회 대상 사용자와 게시글의 `author_id`는 다를 수 있음.

## Post

### 1. GET `/posts`

- **설명**: 게시글 목록 조회. 제목·태그 필터, 정렬, 페이지네이션 지원.

#### Request

| Query Parameter | type | default | 설명 |
| --- | --- | --- | --- |
| `title` | string | 없음 | 제목 부분 일치, 대소문자 구분 없음 |
| `tag` | string | 없음 | 태그 전체 일치, 대소문자 구분 없음 |
| `sort` | string | `created_at` | `created_at` 또는 `view_count` |
| `limit` | integer | `20` | 1~100 |
| `offset` | integer | `0` | 0 이상 |

- URL 예시: `/posts?title=Python&tag=python`, `/posts?sort=view_count&limit=10&offset=0`

#### Response

- **200 OK** — `PostListResponse[]`

```json
[
  {
    "id":2,
    "title":"Python 공부 기록",
    "author_id":6,
    "author_account_id":"test123",
    "author_username":"테스트 유저",
    "author_image_url":null,
    "hashtags":[
      {
        "id":1,
        "name":"python"
      }
    ],
    "like_count":3,
    "comment_count":2,
    "view_count":15,
    "created_at":"2026-11-20T14:20:18+09:00",
    "updated_at":"2026-11-22T14:21:30+09:00"
  }
]
```

#### 비고

- 인증 없이 조회 가능. 삭제되지 않은 게시글만 조회.
- `title`과 `tag`를 함께 전달하면 두 조건 모두 적용.
- `sort=created_at`: `created_at DESC`, `id DESC`.
- `sort=view_count`: `view_count DESC`, `created_at DESC`, `id DESC`.
- 검색 결과가 없으면 `[]`; 잘못된 정렬·페이지네이션 값은 **422**.
- 목록 응답에 `content`, `images`, `is_deleted`는 포함되지 않음.

### 2. POST `/posts`

- **설명**: Markdown 게시글 작성, 이미지 파일 업로드 및 태그 연결

#### Request

- **Headers**: `Content-Type: multipart/form-data`, `Authorization: Bearer <access_token>`
- **Body** — form-data

| key | type | example | 필수 여부 |
| --- | --- | --- | --- |
| `title` | text | `Python 공부 기록` | 필수 |
| `content` | text | `![그래프](upload://graph_abc)` | 필수 |
| `images` | file | `graph.png` | 선택 |
| `image_ids` | text | `graph_abc` | 선택 |
| `hashtags` | text | `Python` | 선택 |

- `title`: 1~200자, 공백만 입력 불가. `content`: 1자 이상, 공백만 입력 불가.
- `images`: 요청당 최대 10개. `image_ids`: 영문 대소문자·숫자·`_`·`-` 허용.
- `hashtags`: 양끝 공백 제거 후 1~50자, 소문자로 정규화하고 중복 제거.
- `images`와 `image_ids`는 같은 순서로 매칭하며 개수가 같아야 함.
- `image_ids`, `hashtags`는 반복 form-data key 또는 JSON 배열 문자열로 전달 가능.

**본문(content) 예시**

```markdown
Python으로 그래프를 만들었습니다.

![그래프](upload://graph_abc)

실행 결과입니다.

![실행 결과](upload://result_xyz)
```

| `image_ids` | `images` |
| --- | --- |
| `graph_abc` | `graph.png` |
| `result_xyz` | `result.png` |

#### Response

- **201 Created** — `PostDetailResponse`

```json
{
  "id":3,
  "title":"Python 공부 기록",
  "author_id":6,
  "author_account_id":"test123",
  "author_username":"테스트 유저",
  "author_image_url":null,
  "hashtags":[
    {
      "id":1,
      "name":"python"
    },
    {
      "id":2,
      "name":"matplotlib"
    }
  ],
  "like_count":0,
  "comment_count":0,
  "view_count":0,
  "created_at":"2026-11-23T14:20:53+09:00",
  "updated_at":"2026-11-23T14:20:53+09:00",
  "content":"Python으로 그래프를 만들었습니다.\n\n![그래프](https://example.com/posts/graph.png?signature=example)\n\n실행 결과입니다.\n\n![실행 결과](https://example.com/posts/result.png?signature=example)",
  "images":[
    {
      "id":10,
      "image_url":"https://example.com/posts/graph.png?signature=example"
    },
    {
      "id":11,
      "image_url":"https://example.com/posts/result.png?signature=example"
    }
  ],
  "is_deleted":false
}
```

#### 비고

- Access Token 인증 필요.
- `upload://{image_id}` 참조는 DB 저장 시 `s3://{object_key}` 내부 참조로 변환됨.
- `post_images.image_url`에는 S3 객체 키를 저장하고, API 응답 시 Presigned URL을 생성함.
- 이미지가 없으면 `images=[]`.
- `image_ids` 중복 불가; 본문의 임시 참조 집합과 `image_ids` 집합이 일치해야 함.
- 새 게시글에서 `s3://` 내부 참조를 직접 사용할 수 없음.
- 이미지 검증 실패 **400**, 요청 검증 실패 **422**, S3 업로드 실패 **502**, DB 충돌 **409**, 기타 DB 오류 **500**.
- 업로드 후 DB 저장 실패 시 업로드된 S3 객체 정리를 시도함.

### 3. GET `/posts/{post_id}`

- **설명**: 게시글 상세 조회. 정상 조회 시 조회수 1 증가.

#### Request

| Path Parameter | type | example |
| --- | --- | --- |
| `post_id` | integer | `3` |

- URL 예시: `/posts/3`

#### Response

- **200 OK** — `PostDetailResponse`

```json
{
  "id":3,
  "title":"Python 공부 기록",
  "author_id":6,
  "author_account_id":"test123",
  "author_username":"테스트 유저",
  "author_image_url":null,
  "hashtags":[
    {
      "id":1,
      "name":"python"
    }
  ],
  "like_count":3,
  "comment_count":2,
  "view_count":16,
  "created_at":"2026-11-20T14:20:53+09:00",
  "updated_at":"2026-11-22T14:22:42+09:00",
  "content":"Python으로 그래프를 만들었습니다.\n\n![그래프](https://example.com/posts/graph.png?signature=example)",
  "images":[
    {
      "id":10,
      "image_url":"https://example.com/posts/graph.png?signature=example"
    }
  ],
  "is_deleted":false
}
```

#### 비고

- 인증 없이 조회 가능. 존재하지 않거나 삭제된 게시글이면 **404**.
- 조회수는 DB에서 원자적으로 1 증가.
- 이미지가 있으면 `content`와 `images`에 Presigned URL 반환.
- 이미지 URL 생성 실패 **502**, 조회수 갱신 DB 오류 **500**.

### 4. PATCH `/posts/{post_id}`

- **설명**: 본인이 작성한 게시글의 제목·본문·이미지·태그 수정

#### Request

- **Headers**: `Content-Type: multipart/form-data`, `Authorization: Bearer <access_token>`

| Path Parameter | type | example |
| --- | --- | --- |
| `post_id` | integer | `3` |

- **Body** — form-data

| key | type | example | 설명 |
| --- | --- | --- | --- |
| `title` | text | `수정된 Python 공부 기록` | 선택 |
| `content` | text | `![새 이미지](upload://new_xyz)` | 선택 |
| `images` | file | `new_result.png` | 새 이미지 파일 |
| `image_ids` | text | `new_xyz` | 새 이미지 임시 참조 ID |
| `keep_image_ids` | text | `10` | 유지할 기존 이미지의 DB ID |
| `hashtags` | text | `Python` | 선택 |

- `title`, `content` 미전달 시 기존 값 유지.
- `keep_image_ids` 미전달 시 기존 이미지 전체 유지; `[]` 전달 시 전체 제거 요청.
- `hashtags` 미전달 시 기존 태그 유지; `[]` 전달 시 태그 전체 제거.
- `image_ids`, `keep_image_ids`, `hashtags`는 반복 form-data key 또는 JSON 배열 문자열 지원.

**이미지 수정 예시**

기존 이미지가 `PostImage.id=10` (`old.png`), `PostImage.id=11` (`remove.png`)일 때, 10번만 유지하고 새 이미지를 추가하려면:

```text
content = 기존 그래프입니다.

![기존 이미지](https://example.com/posts/old.png?signature=example)

![새 이미지](upload://new_xyz)

keep_image_ids = 10
image_ids = new_xyz
images = new_result.png
```

- 기존 이미지 10번은 유지, 11번은 DB 연결 제거.
- 새 이미지는 S3 업로드 및 `PostImage` 생성.
- 기존 Presigned URL은 유지 대상으로 확인되면 `s3://` 내부 참조로 정규화.

#### Response

- **200 OK** — `PostDetailResponse`

```json
{
  "id":3,
  "title":"수정된 Python 공부 기록",
  "author_id":6,
  "author_account_id":"test123",
  "author_username":"테스트 유저",
  "author_image_url":null,
  "hashtags":[
    {
      "id":1,
      "name":"python"
    }
  ],
  "like_count":3,
  "comment_count":2,
  "view_count":16,
  "created_at":"2026-11-20T14:20:53+09:00",
  "updated_at":"2026-11-23T14:22:42+09:00",
  "content":"기존 그래프입니다.\n\n![기존 이미지](https://example.com/posts/old.png?signature=example)\n\n![새 이미지](https://example.com/posts/new_result.png?signature=example)",
  "images":[
    {
      "id":10,
      "image_url":"https://example.com/posts/old.png?signature=example"
    },
    {
      "id":12,
      "image_url":"https://example.com/posts/new_result.png?signature=example"
    }
  ],
  "is_deleted":false
}
```

#### 비고

- Access Token 인증 필요. 작성자가 아니면 **403**, 게시글이 없거나 삭제되었으면 **404**.
- 제목 1~200자, 본문 1자 이상이며 공백만 입력할 수 없음.
- 새 이미지를 추가할 때는 `content`도 전달해야 함.
- 새 이미지 수는 요청당 최대 10개이며 `images`와 `image_ids` 개수가 일치해야 함.
- `image_ids` 중복 불가, 본문 `upload://` 참조와 정확히 대응해야 함.
- `keep_image_ids`는 해당 게시글에 속한 정수 이미지 ID만 허용하며 중복 불가.
- **본문에서 참조하는 기존 이미지는 유지 대상에 포함되어야 함.** 제거하려면 본문 참조도 함께 제거해야 함.
- `keep_image_ids=[]`라도 본문에 기존 이미지 참조가 남아 있으면 **422**.
- `hashtags` 전달 시 전체 교체, `[]` 전달 시 전체 제거.
- 이미지 검증 오류 **400**, 입력 오류 **422**, S3 업로드 오류 **502**, DB 충돌 **409**, 기타 DB 오류 **500**.
- 제거된 기존 이미지의 DB 연결은 삭제하지만 S3 객체는 즉시 삭제하지 않음.
- 이미지 10개 제한은 현재 **한 번의 요청에서 새로 업로드하는 이미지 수**에 적용됨.

### 5. DELETE `/posts/{post_id}`

- **설명**: 본인 게시글 삭제 (Soft Delete)

#### Request

- **Headers**: `Authorization: Bearer <access_token>`

| Path Parameter | type | example |
| --- | --- | --- |
| `post_id` | integer | `3` |

#### Response

- **200 OK**

```json
{
  "detail":"게시글이 삭제되었습니다."
}
```

#### 비고

- 작성자가 아니면 **403**, 게시글이 없거나 이미 삭제되었으면 **404**.
- `posts.is_deleted=True`로 변경하며 게시글 및 S3 이미지 객체를 즉시 물리 삭제하지 않음.
- 삭제된 게시글은 일반 조회 및 수정에서 제외됨.

### 6. POST `/posts/{post_id}/likes`

- **설명**: 게시글 좋아요 등록

#### Request

- **Headers**: `Authorization: Bearer <access_token>`

| Path Parameter | type | example |
| --- | --- | --- |
| `post_id` | integer | `3` |

#### Response

- **200 OK** — `PostLikeResponse`

```json
{
  "post_id":3,
  "like_count":4,
  "is_liked":true
}
```

#### 비고

- 게시글이 없거나 삭제되었으면 **404**, 이미 좋아요했다면 **409**.
- 본인 게시글에도 좋아요 가능.
- `post_likes`에 레코드를 생성하고 `posts.like_count`를 원자적으로 1 증가.
- DB 오류 시 **500**.

### 7. DELETE `/posts/{post_id}/likes`

- **설명**: 게시글 좋아요 취소

#### Request

- **Headers**: `Authorization: Bearer <access_token>`

| Path Parameter | type | example |
| --- | --- | --- |
| `post_id` | integer | `3` |

#### Response

- **200 OK** — `PostLikeResponse`

```json
{
  "post_id":3,
  "like_count":3,
  "is_liked":false
}
```

#### 비고

- 게시글이 없거나 삭제되었으면 **404**, 좋아요 기록이 없으면 **404**.
- `post_likes` 레코드 삭제 및 `posts.like_count` 원자적 1 감소.
- DB 오류 시 **500**.

## Comment

### 1. POST `/posts/{post_id}/comments`

- **설명**: 특정 게시글에 최상위 댓글 작성

#### Request

- **Headers**: `Content-Type: application/json`, `Authorization: Bearer <access_token>`

| Path Parameter | type | example |
| --- | --- | --- |
| `post_id` | integer | `2` |

- URL 예시: `/posts/2/comments`
- **Body** — `CommentCreateRequest`

```json
{
  "content":"첫 번째 댓글입니다."
}
```

- `content` 필수, 1~5,000자, 공백만 입력 불가.

#### Response

- **201 Created** — `CommentResponse`

```json
{
  "id":1,
  "post_id":2,
  "content":"첫 번째 댓글입니다.",
  "author_id":6,
  "author_account_id":"test123",
  "author_username":"테스트 유저",
  "author_image_url":null,
  "parent_comment_id":null,
  "replies":[],
  "created_at":"2026-11-23T00:40:34+09:00",
  "updated_at":"2026-11-23T00:40:34+09:00",
  "is_deleted":false
}
```

#### 비고

- 인증 필요. 게시글이 없거나 삭제되었으면 **404**.
- 내용 누락·공백만 입력·5,000자 초과 시 **422**.
- 최상위 댓글의 `parent_comment_id=null`.
- 생성 시 `posts.comment_count` 원자적 1 증가.
- 작성자 프로필 이미지가 있으면 Presigned URL 반환.
- DB 오류 시 **500**.

### 2. GET `/posts/{post_id}/comments`

- **설명**: 댓글과 대댓글을 최대 2단계 트리 구조로 조회

#### Request

| Path Parameter | type | example |
| --- | --- | --- |
| `post_id` | integer | `2` |

- URL 예시: `/posts/2/comments`

#### Response

- **200 OK** — `CommentResponse[]`

```json
[
  {
    "id":1,
    "post_id":2,
    "content":"첫 번째 댓글입니다.",
    "author_id":6,
    "author_account_id":"test123",
    "author_username":"테스트 유저",
    "author_image_url":null,
    "parent_comment_id":null,
    "replies":[
      {
        "id":3,
        "post_id":2,
        "content":"첫 번째 댓글에 대한 답글입니다.",
        "author_id":8,
        "author_account_id":"anotheruser",
        "author_username":"다른 사용자",
        "author_image_url":null,
        "parent_comment_id":1,
        "replies":[],
        "created_at":"2026-11-23T00:42:00+09:00",
        "updated_at":"2026-11-23T00:42:00+09:00","is_deleted":false
      }
    ],
    "created_at":"2026-11-23T00:40:34+09:00",
    "updated_at":"2026-11-23T00:40:34+09:00",
    "is_deleted":false
  },
  {
    "id":2,
    "post_id":2,
    "content":null,
    "author_id":7,
    "author_account_id":"deletedcommentuser",
    "author_username":"사용자",
    "author_image_url":null,
    "parent_comment_id":null,
    "replies":[],
    "created_at":"2026-11-23T00:41:00+09:00",
    "updated_at":"2026-11-23T00:41:00+09:00",
    "is_deleted":true
  }
]
```

#### 비고

- 인증 없이 조회 가능. 게시글이 없거나 삭제되었으면 **404**.
- 댓글이 없으면 `[]`.
- 최상위 댓글은 바깥 배열에, 대댓글은 부모의 `replies` 배열에 포함됨.
- `created_at ASC`, `id ASC` 순서로 조회해 트리를 구성함.
- 삭제된 댓글도 응답에 포함되며 `content=null`로 반환됨.
- **삭제된 부모 댓글의 기존 대댓글은 유지**됨. 안내 문구는 프론트엔드에서 표시.
- 작성자 프로필 이미지 URL 생성 실패 시 **502**.

### 3. PATCH `/posts/{post_id}/comments/{comment_id}`

- **설명**: 댓글 또는 대댓글 수정 (작성자 본인만 가능)

#### Request

- **Headers**: `Content-Type: application/json`, `Authorization: Bearer <access_token>`

| Path Parameter | type | example |
| --- | --- | --- |
| `post_id` | integer | `2` |
| `comment_id` | integer | `1` |

- URL 예시: `/posts/2/comments/1`
- **Body** — `CommentUpdateRequest`

```json
{
  "content":"이 댓글은 수정되었습니다."
}
```

- `content`는 수정 시 필수, 1~5,000자, `null`·공백만 입력 불가.

#### Response

- **200 OK** — `CommentResponse`

```json
{
  "id":1,
  "post_id":2,
  "content":"이 댓글은 수정되었습니다.",
  "author_id":6,
  "author_account_id":"test123",
  "author_username":"테스트 유저",
  "author_image_url":null,
  "parent_comment_id":null,
  "replies":[],
  "created_at":"2026-11-23T00:40:34+09:00",
  "updated_at":"2026-11-23T00:41:22+09:00",
  "is_deleted":false
}
```

#### 비고

- 인증 필요. 작성자가 아니면 **403**.
- 게시글이 없거나 삭제되었거나, 댓글이 없거나 삭제되었거나 다른 게시글에 속하면 **404**.
- `content` 생략·`null`·공백만 입력·5,000자 초과 시 **422**.
- 댓글과 대댓글 모두 수정 가능; `comment_count`는 변경하지 않음.
- DB 오류 시 **500**.

### 4. DELETE `/posts/{post_id}/comments/{comment_id}`

- **설명**: 댓글 또는 대댓글 삭제 (작성자 본인만 가능, Soft Delete)

#### Request

- **Headers**: `Authorization: Bearer <access_token>`

| Path Parameter | type | example |
| --- | --- | --- |
| `post_id` | integer | `2` |
| `comment_id` | integer | `1` |

- URL 예시: `/posts/2/comments/1`

#### Response

- **200 OK** — `CommentDeleteResponse`

```json
{
  "message":"댓글이 삭제되었습니다."
}
```

#### 비고

- 인증 필요. 작성자가 아니면 **403**.
- 게시글이 없거나 삭제되었거나, 댓글이 없거나 이미 삭제되었으면 **404**.
- 삭제 대상 댓글의 `is_deleted=True`로 변경하며 물리 삭제하지 않음.
- 조회 시 삭제된 댓글의 `content=null`.
- **부모 댓글을 삭제하더라도 기존 대댓글은 삭제하지 않음.**
- `posts.comment_count`는 실제 삭제한 댓글 1개에 대해서만 감소.
- DB 오류 시 **500**.

### 5. POST `/posts/{post_id}/comments/{comment_id}/replies`

- **설명**: 최상위 댓글에 대댓글 작성 (최대 2단계)

#### Request

- **Headers**: `Content-Type: application/json`, `Authorization: Bearer <access_token>`

| Path Parameter | type | example |
| --- | --- | --- |
| `post_id` | integer | `2` |
| `comment_id` | integer | `1` |

- URL 예시: `/posts/2/comments/1/replies`
- **Body** — `CommentCreateRequest`

```json
{
  "content":"이것은 대댓글입니다."
}
```

- `content` 필수, 1~5,000자, 공백만 입력 불가.

#### Response

- **201 Created** — `CommentResponse`

```json
{
  "id":4,
  "post_id":2,
  "content":"이것은 대댓글입니다.",
  "author_id":8,
  "author_account_id":"anotheruser",
  "author_username":"다른 사용자",
  "author_image_url":null,
  "parent_comment_id":1,
  "replies":[],
  "created_at":"2026-11-23T00:41:55+09:00",
  "updated_at":"2026-11-23T00:41:55+09:00",
  "is_deleted":false
}
```

#### 비고

- 인증 필요. 게시글이나 부모 댓글이 없거나 삭제되었거나 다른 게시글에 속하면 **404**.
- 대댓글에 다시 대댓글을 작성하려면 **400 Bad Request**.
- 내용 누락·공백만 입력·5,000자 초과 시 **422**.
- `parent_comment_id`에 부모 댓글 ID 저장, `posts.comment_count` 원자적 1 증가.
- DB 오류 시 **500**.
