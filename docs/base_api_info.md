| 구분 | HTTP | Endpoint | 설명 | JWT 인증 |
| ---- | ---- | -------- | ---- | ----- |
| Auth ( 회원가입 / 로그인 / 탈퇴 ) | | | | |
|      | POST | /auth/signup | 회원가입 (ID, password) | X |
|      | POST | /auth/login | 로그인 | X |
|      | POST | /auth/logout | 로그아웃 | O |
|      | DELETE | /auth/withdraw | 회원 탈퇴 | O |
|      | POST | /auth/refresh | Refresh Token으로 새 Access Token 발급 | O |
| User ( 사용자 프로필 관련 ) | | | | |
|      | GET | /users/me | 내 프로필 조회 | O |
|      | PATCH | /users/me | 내 프로필 수정 | O |
|      | GET | /users/{user_id} | 특정 사용자 프로필 조회 | X |
|      | GET | /users/{user_id}/posts | 특정 사용자의 게시글 목록 | X |
|      | GET | /users/{user_id}/likes/posts | 특정 사용자가 좋아요한 게시글 목록 | X |
| Post ( 게시글 관련 ) | | | | |
|      | GET | /posts | 게시글 목록 조회. title(제목), tag(해시태그)로 필터링 가능. sort, limit, offset 지원 | X |
|      | POST | /posts | 게시글 작성. 텍스트, 코드블럭, 이미지 첨부 가능 | O |
|      | GET | /posts/{post_id} | 게시글 상세 조회 | X |
|      | PATCH | /posts/{post_id} | 게시글 수정 | O |
|      | DELETE | /posts/{post_id} | 게시글 삭제 | O |
|      | POST | /posts/{post_id}/likes | 게시글 좋아요 등록 | O |
|      | DELETE | /posts/{post_id}/likes | 게시글 좋아요 취소 | O |
| Comment ( 댓글 관련 ) | | | | |
|      | GET | /posts/{post_id}/comments | 특정 게시글의 댓글 목록 조회 | X |
|      | POST | /posts/{post_id}/comments | 게시글에 댓글 작성 | O |
|      | PATCH | /posts/{post_id}/comments/{comment_id} | 댓글 수정 | O |
|      | DELETE | /posts/{post_id}/comments/{comment_id} | 댓글 삭제 | O |
|      | POST | /posts/{post_id}/comments/{comment_id}/replies | 대댓글 작성 | O |