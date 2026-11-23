## 요구사항
```
1. 인증 / 회원 관리

- 회원가입, 로그인, 로그아웃, 회원 탈퇴

- JWT 기반 인증

- 자신의 프로필 조회, 수정

- 특정 회원의 게시글 목록 조회

- 특정 회원이 좋아요한 게시글 목록 조회


2. 게시글

- 게시글 조회. 제목, 태그로 필터링 가능, 조회수 내림차순(많은 것부터 적은 순)으로 정렬 가능

- 게시글 작성, 상세 조회, 수정, 삭제

- 게시글 좋아요 등록, 취소


3. 댓글

- 특정 게시글의 댓글 목록 조회

- 댓글 작성, 수정, 삭제

- 대댓글 작성
```

## 프로젝트 구조
```
project_root/
│
├── .gitignore
├── requirements.txt
├── pytest.ini
├── main.py              ← FastAPI 실행 진입점
├── alembic.ini
├── README.md
├── tests/               ← 테스트용 스크립트
│   ├── test_auth.py
│   ├── test_comment.py
│   ├── test_post.py
│   ├── test_s3_connection.py
│   ├── test_s3.py
│   ├── test_schemas.py
│   ├── test_security.py
│   └── test_user.py
│ 
├── app/
│   ├── database.py          ← DB 연결 설정
│   │
│   ├── models/              ← ORM 모델	
│   │     ├── __init__.py
│   │     ├── comment.py
│   │     ├── post_image.py
│   │     ├── post_like.py
│   │     ├── post_tag.py
│   │     ├── post.py
│   │     ├── session.py
│   │     ├── tag.py
│   │     └── user.py
│   │   
│   │
│   ├── schemas/        ← Pydantic 스키마
│   │     ├── __init__.py
│   │     ├── auth.py
│   │     ├── comment.py
│   │     ├── post.py
│   │     ├── tag.py
│   │     └── user.py
│   │
│   ├── routers/
│   │     ├── __init__.py
│   │     ├── auth.py
│   │     ├── comment.py
│   │     ├── post.py
│   │     └── user.py
│   │
│   └── core/
│   │     ├── dependencies.py
│   │     └── security.py
│   │
│   └── services/
│         ├── __init__.py
│         └── s3.py
│
├── docs/
│   ├── base_api_info.md          ← API 명세 표
│   ├── api_상세.md               ← API 상세 정보
│   ├── api_상세_02.md
│   └── ERD_상세.md
│
├── images/
│   └── agent_cs_diagram.png      ← ERD 이미지
│
└── migrations/                   ← Alembic으로 DB 관리
    ├── env.py
    ├── README
    ├── script.py.mako
    └── versions/                 ← Alembic revision 버전
```