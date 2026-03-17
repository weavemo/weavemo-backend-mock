import json
import os
import random
from typing import Dict, List

from fastapi import HTTPException

RARITY_WEIGHTS: Dict[str, int] = {
    "white": 55,
    "gray": 28,
    "black": 12,
    "gold": 5,
}

_ALLOWED_RARITIES = set(RARITY_WEIGHTS.keys())
_ALLOWED_TYPES = {"frame"}  # 지금은 프레임만


def _data_path(filename: str) -> str:
    base_dir = os.path.dirname(os.path.dirname(__file__))  # weavemo-backend-mock/
    return os.path.join(base_dir, "data", filename)


def _load_rewards() -> List[dict]:
    path = _data_path("zen_rewards.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=500, detail=f"Missing rewards data file: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            rewards = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read rewards data: {e}")

    if not isinstance(rewards, list) or not rewards:
        raise HTTPException(status_code=500, detail="Rewards data must be a non-empty JSON array")

    # 최소 검증
    for r in rewards:
        if not isinstance(r, dict):
            raise HTTPException(status_code=500, detail="Each reward must be an object")
        for k in ("id", "type", "rarity", "level", "name"):
            if k not in r:
                raise HTTPException(status_code=500, detail=f"Reward missing field '{k}': {r}")

        if r["rarity"] not in _ALLOWED_RARITIES:
            raise HTTPException(status_code=500, detail=f"Invalid rarity '{r['rarity']}' in reward: {r}")

        if r["type"] not in _ALLOWED_TYPES:
            raise HTTPException(status_code=500, detail=f"Invalid type '{r['type']}' in reward: {r}")

        if not isinstance(r["level"], int) or r["level"] < 1:
            raise HTTPException(status_code=500, detail=f"Invalid level '{r['level']}' in reward: {r}")

    return rewards


def _build_reward_pool(rewards: List[dict]) -> Dict[str, List[dict]]:
    pool: Dict[str, List[dict]] = {k: [] for k in RARITY_WEIGHTS.keys()}
    for r in rewards:
        pool[r["rarity"]].append(r)
    return pool


def roll_capsule_reward(user_id: str) -> dict:
    rewards = _load_rewards()
    pool = _build_reward_pool(rewards)

    rarity = random.choices(
        list(RARITY_WEIGHTS.keys()),
        weights=list(RARITY_WEIGHTS.values()),
        k=1
    )[0]

    rarity_pool = pool.get(rarity, [])
    if not rarity_pool:
        # 해당 rarity가 비었으면 전체에서 뽑되, 서버 크래시 방지
        return random.choice(rewards)

    return random.choice(rarity_pool)
