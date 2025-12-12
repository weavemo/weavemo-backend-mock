# weavemo-backend-mock
pre version for the backend server

1️⃣ DB 접근은 단 하나의 통로만
# db/database.py
def get_supabase(): ...


❌ psycopg2 직접 연결
❌ ORM session
❌ 다른 client 생성

👉 모든 DB I/O는 여기서만

2️⃣ models는 “DB 접근 코드 없음”
# models/user.py
class User:
    id: UUID
    email: str
    nickname: str


✔ 개념 정의
✔ 타입 힌트
✔ 도메인 언어 통일

❌ insert / select
❌ relationship
❌ session

3️⃣ schemas는 API 계약 전용
class UserResponse(BaseModel):
    id: UUID
    email: str


❌ DB 로직
❌ 비즈니스 판단

4️⃣ routers는 얇게, services로 위임
@router.post("/login")
def login(...):
    return auth_service.login(...)



5️⃣ 인증/권한은 Supabase에 위임

❌ JWT 직접 발급
❌ password hash 직접 관리

✔ Supabase Auth
✔ RLS

# .env 예시
ENV=local

SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxxx

JWT_SECRET=dev-secret

