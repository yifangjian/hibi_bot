import threading

from supabase import create_client, Client

from app.config import settings

_thread_local = threading.local()


def _get_client() -> Client:
    """每個執行緒各自建立、重複使用自己的 Client。supabase-py 底層用 httpx，且這個環境有
    裝 h2（HTTP/2），HTTP/2 的連線多工在多個真正的 OS 執行緒間共用同一個連線並不安全
    （只有 async 的單執行緒協作式併發才安全）——實測過，多執行緒共用同一個 Client
    會在併發查詢時穩定重現 httpx.ReadError。改成每個執行緒各自的 Client 就不會有這個問題，
    同一個執行緒內的多次呼叫仍然共用、重複利用連線。
    """
    if not hasattr(_thread_local, "client"):
        _thread_local.client = create_client(settings.supabase_url, settings.supabase_key)
    return _thread_local.client


class _SupabaseProxy:
    def __getattr__(self, name):
        return getattr(_get_client(), name)


supabase: Client = _SupabaseProxy()  # type: ignore[assignment]
