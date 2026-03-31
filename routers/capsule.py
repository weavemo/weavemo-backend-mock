# routers/capsule.py

from fastapi import APIRouter, Depends, HTTPException
from core.capsule_balance import calculate_duplicate_dust
from services.capsule_service import roll_capsule_reward
from dependencies.auth import get_current_user  # 🔥 추가

router = APIRouter()


@router.post("/draw")
def draw_capsule(current_user=Depends(get_current_user)):
    user_id = current_user["user_id"]
    reward = roll_capsule_reward(user_id)
    

    # 1) 캡슐 차감 / 포인트 차감
    # 2) reward roll
    # 3) is_new 판정
    # 아래는 예시 변수명
    reward = roll_capsule_reward(user_id)  
    # reward 예시:
    # {
    #   "id": "zen_crane_fragment_01",
    #   "type": "fragment",
    #   "rarity": "rare",
    #   "level": 3,
    #   "name": "Crane Fragment"
    # }

    is_new = check_user_has_reward(user_id, reward["id"]) is False

    dust = 0

    if is_new:
        grant_reward_to_user(user_id, reward)
    else:
        dust = calculate_duplicate_dust(
            reward.get("rarity", "common"),
            reward.get("level", 1),
        )
        add_dust_to_user(user_id, dust)

    return {
        "ok": True,
        "reward": {
            "id": reward["id"],
            "type": reward.get("type"),
            "rarity": reward.get("rarity", "common"),
            "level": reward.get("level", 1),
            "name": reward.get("name"),
        },
        "is_new": is_new,
        "dust": dust,
    }
