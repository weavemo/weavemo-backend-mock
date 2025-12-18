from datetime import date

DAILY_XP_CAP = 150
LEVEL_CUTOFFS = [0,100,200,300,400,500,600,700,800,900]


def calculate_level(xp: int) -> int:
    level = 1
    for i, cutoff in enumerate(LEVEL_CUTOFFS):
        if xp >= cutoff:
            level = i + 1
    return min(level, 10)


def apply_daily_xp(daily_xp: int, amount: int):
    allowed = max(0, DAILY_XP_CAP - daily_xp)
    gained = min(amount, allowed)
    return daily_xp + gained, gained


def calc_streak(last_date, today: date):
    if last_date == today:
        return 0
    if last_date == today.fromordinal(today.toordinal() - 1):
        return 1
    return -1
