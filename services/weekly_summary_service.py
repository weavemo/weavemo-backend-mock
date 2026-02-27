# weavemo-backend-mock/services/weekly_summary_service.py

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional


DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _parse_week_start(week_start: str) -> date:
    # expects YYYY-MM-DD
    return date.fromisoformat(week_start)


def _week_range_utc(week_start: date) -> tuple[str, str]:
    """
    weekly_summaries.week_start is a date (local concept).
    For now we aggregate using UTC timestamps (recorded_at) from week_start 00:00:00 to +7d.
    """
    start_dt = datetime.combine(week_start, datetime.min.time())
    end_dt = start_dt + timedelta(days=7)
    return start_dt.isoformat(), end_dt.isoformat()


def build_weekly_summary(
    *,
    supabase,
    user_id: int,
    week_start: str,
) -> Dict[str, Any]:
    ws = _parse_week_start(week_start)
    start_iso, end_iso = _week_range_utc(ws)

    # 1) moods in week
    moods_res = (
        supabase.table("moods")
        .select("id, recorded_at, main_valence, energy")
        .eq("user_id", user_id)
        .gte("recorded_at", start_iso)
        .lt("recorded_at", end_iso)
        .execute()
    )
    moods: List[Dict[str, Any]] = moods_res.data or []

    if not moods:
        # keep prior frontend behavior: null-ish fields but still a stable object
        return {
            "user_id": user_id,
            "week_start": week_start,
            "avg_valence": None,
            "avg_energy": None,
            "top_emotions": None,
            "weekday_pattern": None,
            "summary_text": None,
            "journal_days": None,
            "mood_checks": 0,
            "points_gained": None,
            "points_possible": None,
        }

    # averages
    v_vals = [m["main_valence"] for m in moods if m.get("main_valence") is not None]
    e_vals = [m["energy"] for m in moods if m.get("energy") is not None]
    avg_valence = (sum(v_vals) / len(v_vals)) if v_vals else None
    avg_energy = (sum(e_vals) / len(e_vals)) if e_vals else None

    # weekday pattern (UTC 기준; 최소 수정)
    by_wd: Dict[int, Dict[str, float]] = {}  # 0..6
    for m in moods:
        ra = m.get("recorded_at")
        if not ra:
            continue
        # recorded_at is ISO; datetime.fromisoformat expects no Z
        dt = datetime.fromisoformat(ra.replace("Z", ""))
        wd = dt.weekday()  # Mon=0
        cur = by_wd.get(wd) or {"vSum": 0.0, "eSum": 0.0, "n": 0.0}
        cur["vSum"] += float(m.get("main_valence") or 0)
        cur["eSum"] += float(m.get("energy") or 0)
        cur["n"] += 1.0
        by_wd[wd] = cur

    weekday_pattern: List[Dict[str, Any]] = []
    for wd in range(7):
        if wd not in by_wd or by_wd[wd]["n"] <= 0:
            continue
        agg = by_wd[wd]
        weekday_pattern.append(
            {
                "day": DAY_NAMES[wd],
                "valence": agg["vSum"] / agg["n"],
                "energy": agg["eSum"] / agg["n"],
            }
        )
    # top_emotions (tag counts)
    # ✅ join/embed 형태에 의존하지 않고 tag_id를 직접 카운트 → emotion_tags에서 code 매핑
    top_emotions = []
    try:
        mood_ids = [m["id"] for m in moods if m.get("id") is not None]
        if mood_ids:
            joins_res = (
                supabase.table("mood_emotion_tags")
                .select("tag_id")
                .in_("mood_id", mood_ids)
                .execute()
            )

            tag_counts: Dict[int, int] = {}
            for r in joins_res.data or []:
                tid = r.get("tag_id")
                if tid is None:
                    continue
                tag_counts[int(tid)] = tag_counts.get(int(tid), 0) + 1

            if tag_counts:
                tag_ids = list(tag_counts.keys())
                tags_res = (
                    supabase.table("emotion_tags")
                    .select("id, code")
                    .in_("id", tag_ids)
                    .execute()
                )
                id_to_code = {int(t["id"]): t["code"] for t in (tags_res.data or []) if t.get("id") and t.get("code")}

                top_emotions = [
                    {"code": id_to_code[tid], "count": cnt}
                    for tid, cnt in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
                    if tid in id_to_code
                ][:5]
    except Exception:
        # best-effort: 실패 시 빈 배열 유지
        top_emotions = []

    mood_checks = len(moods)

    # 2) journals_days — best-effort (table/columns may differ)
    journal_days = None
    try:
        j_res = (
            supabase.table("journals")
            .select("date")
            .eq("user_id", user_id)
            .gte("date", week_start)
            .lt("date", (ws + timedelta(days=7)).isoformat())
            .execute()
        )
        dates = {r["date"] for r in (j_res.data or []) if r.get("date")}
        journal_days = len(dates)
    except Exception:
        journal_days = None

    # 3) points — 최소 규칙 (나중에 XP로 교체 가능)
    points_gained = None
    points_possible = None
    if journal_days is not None:
        # mood 10점/회, journal 20점/일 (임시 규칙)
        points_gained = mood_checks * 10 + journal_days * 20
        # 최대: mood 하루 1회 가정(7회) + journal 하루 1회(7일)
        points_possible = 7 * 10 + 7 * 20

    # 4) summary_text (템플릿)
    summary_text = None
    if avg_valence is not None and avg_energy is not None:
        if avg_valence >= 0.8:
            tone = "전반적으로 긍정적인 한 주였어요."
        elif avg_valence <= -0.8:
            tone = "마음이 무거운 날이 많았던 한 주였어요."
        else:
            tone = "감정 기복이 크지 않았던 한 주였어요."

        if avg_energy >= 4:
            energy_line = "에너지가 높게 유지되는 편이었어요."
        elif avg_energy <= 2:
            energy_line = "에너지가 낮게 느껴진 날이 많았어요."
        else:
            energy_line = "에너지는 중간 정도로 유지됐어요."

        summary_text = f"{tone} {energy_line}"

    return {
        "user_id": user_id,
        "week_start": week_start,
        "avg_valence": avg_valence,
        "avg_energy": avg_energy,
        "top_emotions": top_emotions,
        "weekday_pattern": weekday_pattern or None,
        "summary_text": summary_text,
        "journal_days": journal_days,
        "mood_checks": mood_checks,
        "points_gained": points_gained,
        "points_possible": points_possible,
    }
