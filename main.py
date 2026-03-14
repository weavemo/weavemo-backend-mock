# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, user, mood, stats, action, journal, badge, journal_entries, weekly_summaries
from routers.posts import router as posts_router
from routers.comments import router as comments_router
from routers.comments_actions import router as comments_actions_router

app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://www.localhost:5173",
    "http://127.0.0.1:5173",
]

# ⭐ CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # 개발 단계에서는 전체 허용 O
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
app.include_router(badge.router, prefix="/badges", tags=["badges"])
app.include_router(journal_entries.router, prefix="/journal-entries", tags=["JournalEntries"])
app.include_router(weekly_summaries.router, tags=["WeeklySummaries"])
app.include_router(posts_router)
app.include_router(comments_router)
app.include_router(comments_actions_router)
