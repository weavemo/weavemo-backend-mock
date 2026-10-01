# file: services/collection_service.py

from db.database import get_supabase


def complete_action(auth_uid: str, collection_key: str):
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
            "p_user_id": auth_uid,
            "p_collection_id": collection_id
        }
    ).execute()

    return {
        "fragment_id": result.data
    }


# file: weavemo-backend-mock/services/collection_service.py
def get_collections(auth_uid: str):
    supabase = get_supabase()

    result = (
        supabase.table("collections")
        .select("""
            id,
            key,
            name,
            total_fragments,
            collection_fragments(id, key, name, fragment_order),
            collection_rewards(
                reward_items(key, name)
            )
        """)
        .eq("is_active", True)
        .execute()
    )

    collections = result.data or []

    owned_res = (
        supabase.table("user_fragment_inventory")
        .select("fragment_id")
        .eq("user_id", auth_uid)
        .gt("quantity", 0)
        .execute()
    )
    owned_ids = {
        str(row["fragment_id"])
        for row in owned_res.data or []
    }

    for collection in collections:
        fragments = collection.get("collection_fragments") or []
        fragments.sort(key=lambda f: f["fragment_order"])

        for fragment in fragments:
            fragment["owned"] = str(fragment["id"]) in owned_ids

    return collections


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
