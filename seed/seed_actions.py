from db.database import get_supabase

def seed_actions():
    supabase = get_supabase()

    actions = [
        {
            "id": 1,
            "title": "Take 3 deep breaths",
            "type": "breathing",
            "description": "Slow your breathing and relax your body.",
            "duration_min": 1,
            "difficulty": 1,
            "is_premium": False,
            "is_active": True,
        }
    ]

    for action in actions:
        supabase.table("actions").upsert(action).execute()

if __name__ == "__main__":
    seed_actions()
