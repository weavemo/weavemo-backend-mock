# Weavemo Backend – Folder Structure v1

This is the official backend architecture template for the Weavemo project  
(FastAPI + Supabase + Clean Architecture).

---

## 📁 Root Structure
weavemo-backend/
│
├── main.py
├── requirements.txt
├── .env # DATABASE_URL, JWT_SECRET, etc.
│
├── db/
│ ├── database.py # Supabase DB connection
│ ├── fake_db.py # Mock DB (temporary, will be removed later)
│
├── models/
│ ├── init.py
│ ├── base.py # Base model (id, timestamps)
│ ├── user.py # users, user_stats ORM
│ ├── mood.py # moods, triggers, emotion_tags, mood_analysis
│ ├── journal.py # journals + journal_analysis
│ ├── action.py # actions + action_logs
│ ├── badge.py # badges + user_badges
│ ├── skin.py # skins + user_skins
│ ├── community.py # posts, comments, post_likes
│ ├── subscription.py # subscriptions
│ ├── notification.py # notifications
│
├── schemas/
│ ├── init.py
│ ├── base.py
│ ├── auth.py
│ ├── user.py
│ ├── mood.py
│ ├── journal.py
│ ├── action.py
│ ├── badge.py
│ ├── community.py
│ ├── subscription.py
│ ├── notification.py
│
├── routers/
│ ├── init.py
│ ├── auth.py # login, logout, register
│ ├── user.py # get/update profile, stats
│ ├── mood.py # create mood, retrieve history
│ ├── journal.py # create journal, read journal
│ ├── action.py # recommended actions
│ ├── badge.py # badge list
│ ├── community.py # posts, comments, likes
│ ├── subscription.py # premium subscription
│ ├── notification.py # user notifications
│
├── services/
│ ├── ai/
│ │ ├── mood_analysis.py # emotion model
│ │ ├── journal_analysis.py # journal summary
│ │ └── crisis_detection.py # risk detection
│ │
│ ├── auth_service.py
│ ├── user_service.py
│ ├── mood_service.py
│ ├── journal_service.py
│ ├── action_service.py
│ ├── community_service.py
│
├── utils/
│ ├── password.py
│ ├── jwt.py
│ ├── timezone.py
│ ├── pagination.py
│ ├── middleware.py
│
├── tests/
│ ├── unit/
│ ├── integration/
│ ├── conftest.py
│
├── config/
│ ├── logging.py
│ ├── settings.py # Pydantic settings class
│
└── docs/
├── API_SPEC.md
├── DB_SCHEMA.md
├── README.md

## ✔ Notes
- This structure is optimized for **scalability, clarity, and separation of concerns**.
- Every domain (mood, journal, actions…) has:
  - `model`
  - `schema`
  - `router`
  - `service`  
  → **Perfect separation**.
- `config/settings.py` handles all environment variables.
- `db/database.py` connects directly to Supabase PostgreSQL.
