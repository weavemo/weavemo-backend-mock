# file: services/collection_service.py

from db.database import get_supabase


# file: services/collection_service.py

# file: services/collection_service.py

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
        .order("key")
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
            fragment["owned"] = str(fragment["id"]) in owned_ids

        collection["collection_fragments"] = fragments

        # 현재 보상을 먼저 표시하고, 다음 보상으로 최대 4칸 구성
        previews = []
        seen_reward_keys = set()

        def add_rewards(source, is_current):
            for link in source.get("collection_rewards") or []:
                reward = link.get("reward_items")

                if not reward or reward["key"] in seen_reward_keys:
                    continue

                seen_reward_keys.add(reward["key"])

                previews.append({
                    "collection_key": source["key"],
                    "collection_order": source["collection_order"],
                    "is_current": is_current,
                    "reward_items": reward,
                })

        add_rewards(collection, True)

        current_order = collection["collection_order"]

        for upcoming in collections:
            if len(previews) >= 4:
                break

            upcoming_order = upcoming.get("collection_order")

            if (
                upcoming.get("action_type") != collection["action_type"]
                or upcoming_order is None
                or upcoming_order <= current_order
            ):
                continue

            upcoming_fragments = (
                upcoming.get("collection_fragments") or []
            )

            # 조각이 없거나 이미 완성한 컬렉션은 미리보기에서 제외
            if not upcoming_fragments:
                continue

            if all(
                str(fragment["id"]) in owned_ids
                for fragment in upcoming_fragments
            ):
                continue

            for link in upcoming.get("collection_rewards") or []:
                if len(previews) >= 4:
                    break

                reward = link.get("reward_items")

                if not reward or reward["key"] in seen_reward_keys:
                    continue

                seen_reward_keys.add(reward["key"])

                previews.append({
                    "collection_key": upcoming["key"],
                    "collection_order": upcoming_order,
                    "is_current": False,
                    "reward_items": reward,
                })

        collection["reward_previews"] = previews

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
