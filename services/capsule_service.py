# services/capsule_service.py
import random

# TODO: 밸런스 확정되면 여기 값만 조정
RARITY_WEIGHTS = {
    "white": 55,
    "gray": 28,
    "black": 12,
    "gold": 5,
}

# TODO: 실제 reward 데이터(테이블/리스트)로 교체
REWARD_POOL = {
    "white": [],
    "gray": [],
    "black": [],
    "gold": [],
}

def roll_capsule_reward(user_id: str) -> dict:
    rarity = random.choices(
        list(RARITY_WEIGHTS.keys()),
        weights=list(RARITY_WEIGHTS.values()),
        k=1
    )[0]

    pool = REWARD_POOL.get(rarity, [])
    if not pool:
        raise HTTPException(status_code=500, detail=f"REWARD_POOL is empty for rarity='{rarity}'")

    return random.choice(pool)
