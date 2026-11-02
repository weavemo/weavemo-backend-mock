# main.py

from routers import community_blocks
from routers import dust
from routers import friends
from routers import hidden_content
from routers import post_media
from routers import moderation
from routers import presence
from routers import community_reports
from routers import admin_notes
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, user, mood, stats, action, journal, badge, journal_entries, weekly_summaries, zen_art, capsule, collection
from routers.posts import router as posts_router
from routers.comments import router as comments_router
from routers.comments_actions import router as comments_actions_router
from routers.analysis_access import router as analysis_access_router
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from routers import rewards
from routers import notifications
from routers import onboarding
from routers import chat
from routers import notes

app = FastAPI()

Path("uploads/profiles").mkdir(
    parents=True,
    exist_ok=True,
)

app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads",
)

origins = [
    "http://localhost:5173",
    "http://www.localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.1.132:5173",
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
app.include_router(rewards.router, prefix="/rewards", tags=["Rewards"])
app.include_router(journal_entries.router, prefix="/journal-entries", tags=["JournalEntries"])
app.include_router(weekly_summaries.router, tags=["WeeklySummaries"])
app.include_router(posts_router, prefix="/posts", tags=["posts"])
app.include_router(comments_router, prefix="/posts", tags=["comments"])
app.include_router(comments_actions_router, prefix="/comments", tags=["comments"])
app.include_router(zen_art.router, prefix="/zen-art", tags=["zen-art"])
app.include_router(capsule.router, prefix="/capsule", tags=["capsule"])
app.include_router(collection.router, prefix="/collections", tags=["collections"])
app.include_router(analysis_access_router)
app.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"],
)
app.include_router(
    friends.router,
    prefix="/friends",
    tags=["Friends"],
)
app.include_router(
    onboarding.router,
    prefix="/user",
    tags=["Onboarding"],
)
app.include_router(
    chat.router,
    prefix="/chat",
    tags=["Chat"],
)
app.include_router(
    presence.router,
    prefix="/presence",
    tags=["Presence"],
)
app.include_router(
    notes.router,
    prefix="/notes",
    tags=["Notes"],
)
app.include_router(
    admin_notes.router,
    prefix="/admin",
    tags=["Admin"],
)
app.include_router(
    moderation.router,
    prefix="/moderation",
    tags=["Moderation"],
)
app.include_router(
    post_media.router,
    prefix="/posts",
    tags=["PostMedia"],
)
# 게시물·댓글 신고 API를 등록한다.
app.include_router(
    community_reports.router,
    prefix="/posts",
    tags=["CommunityReports"],
)

# 게시물·댓글 작성자 차단 API를 등록한다.
app.include_router(
    community_blocks.router,
    prefix="/posts",
    tags=["CommunityBlocks"],
)

# 본인의 숨긴 콘텐츠 관리 API를 등록한다.
app.include_router(
    hidden_content.router,
    prefix="/community/hidden-content",
    tags=["HiddenContent"],
)

app.include_router(
    dust.router,
    prefix="/dust",
    tags=["Dust"],
)
