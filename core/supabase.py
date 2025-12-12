# core/supabase.py
from supabase import create_client
from config.settings import settings

supabase = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_ROLE_KEY
)
