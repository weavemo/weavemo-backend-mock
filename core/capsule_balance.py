# core/capsule_balance.py

RARITY_BASE_DUST = {
    "common": 12,
    "rare": 20,
    "epic": 32,
    "legendary": 50,
}

LEVEL_DUST_MULTIPLIER = {
    1: 1.00,
    2: 0.92,
    3: 0.85,
    4: 0.78,
    5: 0.72,
}


def get_level_multiplier(level: int) -> float:
    if level in LEVEL_DUST_MULTIPLIER:
        return LEVEL_DUST_MULTIPLIER[level]

    if level > max(LEVEL_DUST_MULTIPLIER.keys()):
        return LEVEL_DUST_MULTIPLIER[max(LEVEL_DUST_MULTIPLIER.keys())]

    return 1.0


def calculate_duplicate_dust(rarity: str, level: int) -> int:
    base = RARITY_BASE_DUST.get(rarity, RARITY_BASE_DUST["common"])
    multiplier = get_level_multiplier(level)
    dust = round(base * multiplier)
    return max(1, dust)
