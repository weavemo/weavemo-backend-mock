from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, user

app = FastAPI()

# ⭐ CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # 개발 단계에서는 전체 허용 O
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth")
app.include_router(user.router, prefix="/user")


