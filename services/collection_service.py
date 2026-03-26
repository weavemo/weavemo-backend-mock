# file: services/collection_service.py

from db.database import get_supabase


def complete_action(user_id: str, collection_key: str):
    supabase = get_supabase()

    # collection 조회
    collection = supabase.table("collections") \
        .select("id") \
        .eq("key", collection_key) \
        .single() \
        .execute()

    if not collection.data:
        raise Exception("Collection not found")

    collection_id = collection.data["id"]

    # RPC 호출
    result = supabase.rpc(
        "complete_action",
        {
            "p_user_id": user_id,
            "p_collection_id": collection_id
        }
    ).execute()

    return {
        "fragment_id": result.data
    }


def get_collections(user_id: str):
    supabase = get_supabase()

    result = supabase.table("collections") \
        .select("""
            id,
            key,
            name,
            collection_fragments(id),
            collection_rewards(
                reward_items(
                    key,
                    name
                )
            )
        """) \
        .execute()

    return result.data


def get_user_behaviors(user_id: str):
    supabase = get_supabase()

    result = supabase.table("user_behavior_unlocks") \
        .select("""
            behaviors (
                id,
                key,
                name,
                description,
                duration
            )
        """) \
        .eq("user_id", user_id) \
        .execute()

    return [b["behaviors"] for b in result.data]
