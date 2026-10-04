import json
import threading

from openai import OpenAI

from app.config import settings

_thread_local = threading.local()


def _get_client() -> OpenAI:
    """每個執行緒各自建立、重複使用自己的 client，原因同 app/db/client.py 的
    _SupabaseProxy：底層 httpx 走 HTTP/2 時，同一個 client 被多個真正的 OS 執行緒同時
    使用並不安全（已用平行請求實測重現過連線層級的 ReadError），改成每個執行緒各自持有
    一個 client 就沒有這個問題。因為現在答題流程會把 AI 呼叫丟到背景執行緒跟 DB 寫入
    平行執行（見 message_router.py／menu_actions.py），加上 webhook 本身也用
    run_in_threadpool 處理不同使用者的請求，chat_completion 很可能被多個執行緒同時
    呼叫，這裡必須是執行緒安全的。
    """
    if not hasattr(_thread_local, "client"):
        _thread_local.client = OpenAI(api_key=settings.openai_api_key)
    return _thread_local.client


def chat_completion(messages: list[dict]) -> str:
    response = _get_client().chat.completions.create(model=settings.openai_model, messages=messages)
    return response.choices[0].message.content


def chat_completion_json(messages: list[dict], schema_name: str, schema: dict) -> dict:
    """要求模型嚴格依 JSON schema 回傳（OpenAI structured outputs）。用在輸出結構必須固定的
    地方：只靠提示詞要求「答對時不要寫某段」「不要重列某個選項」，實測模型不會每次都照做，
    改成分欄位回傳、由程式組裝，結構就不會跑掉。"""
    response = _get_client().chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        response_format={"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
    )
    return json.loads(response.choices[0].message.content)
