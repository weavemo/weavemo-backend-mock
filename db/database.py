# db/database.py

from threading import Lock

import httpx
from supabase import Client, ClientOptions, create_client

from config.settings import settings


_supabase: Client | None = None
_init_lock = Lock()


def get_supabase() -> Client:
    global _supabase

    if _supabase is not None:
        return _supabase

    with _init_lock:
        if _supabase is None:
            http_client = httpx.Client(
                http2=False,
                timeout=httpx.Timeout(
                    30.0,
                    connect=10.0,
                ),
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=0,
                ),
            )

            try:
                _supabase = create_client(
                    settings.SUPABASE_URL,
                    settings.SUPABASE_SERVICE_ROLE_KEY,
                    options=ClientOptions(
                        auto_refresh_token=False,
                        persist_session=False,
                        httpx_client=http_client,
                    ),
                )
            except Exception:
                http_client.close()
                raise

    return _supabase
