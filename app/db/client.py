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

_PAGE_SIZE = 1000


def fetch_all_rows(build_query) -> list[dict]:
    """PostgREST 預設單次查詢最多回傳 1000 筆，不分頁的話會被悄悄截斷、遺漏資料——
    這個 bug 曾經真的發生過：使用者累積作答夠多之後，`attempts_log` 依 user_id 查詢
    的筆數超過 1000 筆，導致某些已作答的題目被截斷、沒被算進「已作答」名單，因而被
    誤判成還沒作答過、重複出現在下一題。任何理論上筆數可能隨使用者活躍度或時間累積到
    超過千筆的查詢（例如依 user_id 查 attempts_log／wrong_question_state，完全沒有
    用 mode／exam_scope 進一步限縮的情況）都應該用這個 helper，不要直接 execute()。

    build_query 是一個不帶 range 的查詢建構函式，每次呼叫要回傳全新的 query builder
    （不能重複使用同一個 query 物件呼叫多次 range，supabase-py 的物件 execute 過一次
    後就不能再用）。
    """
    rows: list[dict] = []
    offset = 0
    while True:
        page = build_query().range(offset, offset + _PAGE_SIZE - 1).execute().data
        rows.extend(page)
        if len(page) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    return rows
