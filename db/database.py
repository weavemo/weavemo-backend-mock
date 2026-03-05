from supabase import create_client, Client
from config.settings import settings
import httpx

_supabase: Client | None = None


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        # Windows에서 http2/read 오류 완화: http2 끄고 timeout 여유
        http_client = httpx.Client(http2=False, timeout=httpx.Timeout(10.0, connect=10.0))
        _supabase = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,  # ⚠️ backend 전용
            options={"http_client": http_client},
        )
    return _supabase
