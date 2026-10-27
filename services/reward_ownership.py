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
