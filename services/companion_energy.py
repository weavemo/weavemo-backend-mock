"""Server-authoritative energy settlement. SQL serializes each user's mutations."""
import math


def load_companion_energy(db, user_id):
    state = db.rpc("get_companion_energy_status", {"p_user_id": user_id}).execute().data
    if not isinstance(state, dict) or state.get("stage") not in ("egg", "hatched", "grown"):
        raise ValueError("Invalid energy status")
    if state["stage"] != "egg":
        energy = state.get("energy")
        if (isinstance(energy, bool) or not isinstance(energy, (int, float))
                or not math.isfinite(energy) or not 0 <= energy <= 100
                or type(state.get("growth_phase")) is not int
                or not 1 <= state["growth_phase"] <= 6
                or not isinstance(state.get("actions"), dict)):
            raise ValueError("Invalid energy values")
    return state
