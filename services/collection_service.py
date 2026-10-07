# file: services/collection_service.py

from db.database import get_supabase


def get_collections(auth_uid: str):
    supabase = get_supabase()

    result = (
        supabase.table("collections")
        .select("""
            id,
            key,
            name,
            name_i18n,
            action_type,
            collection_order,
            total_fragments,
            collection_fragments(
                id,
                key,
                name,
                fragment_order
            ),
            collection_rewards(
                reward_items(key, name)
            )
        """)
        .eq("is_active", True)
        .order("collection_order")
        .execute()
    )

    collections = result.data or []

    action_types = sorted({
        collection["action_type"]
        for collection in collections
        if collection.get("action_type")
    })

    current_ids = set()

    for action_type in action_types:
        current = supabase.rpc(
            "get_current_action_collection",
            {
                "p_auth_uid": auth_uid,
                "p_action_type": action_type,
            },
        ).execute()

        if current.data:
            current_ids.add(str(current.data))

    current_collections = [
        collection
        for collection in collections
        if str(collection["id"]) in current_ids
    ]

    if not current_collections:
        return []

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

    for collection in current_collections:
        fragments = collection.get("collection_fragments") or []
        fragments.sort(
            key=lambda fragment: fragment["fragment_order"]
        )

        for fragment in fragments:
            fragment["owned"] = (
                str(fragment["id"]) in owned_ids
            )

        collection["collection_fragments"] = fragments

    return current_collections


def get_user_behaviors(user_id: int):
    supabase = get_supabase()

    result = (
        supabase.table("user_behavior_unlocks")
        .select("""
            behaviors(
                id,
                key,
                name,
                description,
                duration
            )
        """)
        .eq("user_id", user_id)
        .execute()
    )

    return [
        row["behaviors"]
        for row in result.data or []
        if row.get("behaviors") is not None
    ]
