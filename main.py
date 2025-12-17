from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, user, mood, stats, action, journal

app = FastAPI()

# ⭐ CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # 개발 단계에서는 전체 허용 O
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(user.router, prefix="/user", tags=["Users"])
app.include_router(mood.router, prefix="/mood", tags=["Mood"])
app.include_router(stats.router,prefix="/stats",tags=["Stats"])
app.include_router(action.router, prefix="/actions", tags=["actions"])
app.include_router(journal.router, prefix="/journals", tags=["Journal"])



