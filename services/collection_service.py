# services/collection_service.py

from db.database import get_supabase


def get_collections(auth_uid: str):
    supabase = get_supabase()

    user_res = (
        supabase.table("users")
        .select("plan")
        .eq("auth_uid", auth_uid)
        .limit(1)
        .execute()
    )

    if not user_res.data:
        raise ValueError("User not found")

    is_subscriber = (
        user_res.data[0].get("plan") == "premium"
    )

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
            is_premium,
            is_master,
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

    eligible_collections = []

    for collection in collections:
        fragments = (
            collection.get("collection_fragments") or []
        )

        fragments.sort(
            key=lambda fragment:
                fragment["fragment_order"]
        )

        for fragment in fragments:
            fragment["owned"] = (
                str(fragment["id"]) in owned_ids
            )

        collection["collection_fragments"] = fragments

        requires_subscription = bool(
            collection.get("is_premium")
            and not is_subscriber
        )

        collection["subscription_required"] = (
            requires_subscription
        )
        collection["can_collect"] = (
            not requires_subscription
        )

        # 조각과 보상이 있는 행동 컬렉션만 표시 대상으로 사용
        if (
            collection.get("action_type")
            and collection.get("collection_order") is not None
            and fragments
            and collection.get("collection_rewards")
        ):
            eligible_collections.append(collection)

    # 행동별 첫 미완성 컬렉션.
    # 잠긴 컬렉션을 건너뛰지 않아 구독 미리보기가 유지된다.
    current_collections = []
    selected_actions = set()

    for collection in eligible_collections:
        action_type = collection["action_type"]

        if action_type in selected_actions:
            continue

        fragments = collection["collection_fragments"]

        if all(fragment["owned"] for fragment in fragments):
            continue

        selected_actions.add(action_type)
        current_collections.append(collection)

    for collection in current_collections:
        previews = []
        seen_reward_keys = set()

        def add_rewards(source, is_current):
            for link in source.get("collection_rewards") or []:
                if len(previews) >= 4:
                    break

                reward = link.get("reward_items")

                if (
                    not reward
                    or reward["key"] in seen_reward_keys
                ):
                    continue

                seen_reward_keys.add(reward["key"])

                previews.append({
                    "collection_key": source["key"],
                    "collection_order":
                        source["collection_order"],
                    "is_current": is_current,
                    "is_premium":
                        bool(source.get("is_premium")),
                    "is_master":
                        bool(source.get("is_master")),
                    "subscription_required":
                        source["subscription_required"],
                    "reward_items": reward,
                })

        add_rewards(collection, True)

        current_position = (
            collection["collection_order"],
            collection["key"],
        )

        for upcoming in eligible_collections:
            if len(previews) >= 4:
                break

            if (
                upcoming["action_type"]
                != collection["action_type"]
            ):
                continue

            upcoming_position = (
                upcoming["collection_order"],
                upcoming["key"],
            )

            if upcoming_position <= current_position:
                continue

            if all(
                fragment["owned"]
                for fragment in upcoming["collection_fragments"]
            ):
                continue

            add_rewards(upcoming, False)

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
