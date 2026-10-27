# weavemo-backend-mock/services/reward_ownership.py

def owned_reward_keys(
    supabase,
    auth_uid: str,
) -> set[str]:
    inventory = (
        supabase.table("user_reward_inventory")
        .select("reward_item_id")
        .eq("user_id", auth_uid)
        .execute()
    )

    item_ids = list({
        row["reward_item_id"]
        for row in inventory.data or []
    })

    if not item_ids:
        return set()

    items = (
        supabase.table("reward_items")
        .select("key")
        .in_("id", item_ids)
        .execute()
    )

    return {
        item["key"]
        for item in items.data or []
    }


def valid_equipped_frame(
    frame: str | None,
    owned: set[str],
) -> str | None:
    if not frame or frame == "none":
        return None

    return frame if f"frame_{frame}" in owned else None

# weavemo-backend-mock/services/reward_ownership.py
# 기존 코드 맨 아래에 추가

def profile_equipment_by_user(
    supabase,
    users: list[dict],
) -> dict[int, dict]:
    if not users:
        return {}

    user_ids = [user["id"] for user in users]
    auth_uids = [
        user["auth_uid"]
        for user in users
        if user.get("auth_uid")
    ]

    stats_result = (
        supabase.table("user_stats")
        .select("user_id, equipped_frame, equipped_badge")
        .in_("user_id", user_ids)
        .limit(len(user_ids))
        .execute()
    )

    stats_by_id = {
        row["user_id"]: row
        for row in stats_result.data or []
    }

    owned_by_auth = {
        auth_uid: set()
        for auth_uid in auth_uids
    }

    # 여러 친구의 보유 보상을 함께 조회한다.
    if auth_uids:
        offset = 0
        page_size = 1000

        while True:
            inventory_result = (
                supabase.table("user_reward_inventory")
                .select("user_id, reward_item_id, reward_items(key)")
                .in_("user_id", auth_uids)
                .order("user_id")
                .order("reward_item_id")
                .range(offset, offset + page_size - 1)
                .execute()
            )

            rows = inventory_result.data or []

            for row in rows:
                reward = row.get("reward_items")

                if not isinstance(reward, dict):
                    continue

                key = reward.get("key")

                if isinstance(key, str):
                    owned_by_auth.setdefault(
                        row["user_id"],
                        set(),
                    ).add(key)

            if len(rows) < page_size:
                break

            offset += page_size

    equipment = {}

    for user in users:
        stats = stats_by_id.get(user["id"], {})
        owned = owned_by_auth.get(
            user.get("auth_uid"),
            set(),
        )

        equipment[user["id"]] = {
            "equipped_frame": valid_equipped_frame(
                stats.get("equipped_frame"),
                owned,
            ),
            "equipped_badge": stats.get("equipped_badge"),
        }

    return equipment
