# services/hidden_content.py

from typing import Literal


def get_hidden_content_ids(
    supabase,
    user_id: int,
    content_kind: Literal["post", "comment"],
    candidate_ids: list[int],
) -> set[int]:
    """조회 후보 중 현재 사용자가 숨긴 항목 번호만 반환한다."""
    ids = sorted({int(value) for value in candidate_ids})

    if not ids:
        return set()

    target_column = (
        "post_id"
        if content_kind == "post"
        else "comment_id"
    )

    hidden_ids: set[int] = set()

    # 조회 주소가 길어지지 않도록 후보를 나눠 조회한다.
    for start in range(0, len(ids), 200):
        batch = ids[start:start + 200]

        result = (
            supabase.table("user_hidden_content")
            .select(target_column)
            .eq("user_id", int(user_id))
            .eq("content_kind", content_kind)
            .in_(target_column, batch)
            .limit(len(batch))
            .execute()
        )

        hidden_ids.update(
            int(row[target_column])
            for row in (result.data or [])
            if row.get(target_column) is not None
        )

    return hidden_ids
