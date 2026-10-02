"""開通碼：研究者確認名單後發給實驗組同學／測試人員，一組碼只能綁定一個 LINE 帳號。

設計重點：
- 資料庫只記「哪組碼綁了哪個使用者」，不存學號或姓名。碼跟學號的對照表由研究者自己
  保管在本機（generate_access_codes.py 輸出的 CSV），比對問卷時用學號，不再依賴 LINE
  顯示名稱——之前靠顯示名稱比對，使用者中途改名就會被誤判成非參與者。
- 兌換是單一條件式 UPDATE（只更新 user_id 仍是 NULL 且未作廢的那一列），兩個人同時輸入
  同一組碼時，Postgres 會讓第二個人的 UPDATE 重新檢查條件、更新 0 列，所以只有一個人會成功。
- 不做輸錯鎖定：6 碼、31 個字元約 8.9 億種組合，一學期發出的碼只有幾十組，在 LINE 聊天室
  一次一次打字猜中的機率可以忽略，不值得為此多一張表跟一段狀態邏輯。
"""

import secrets
import unicodedata
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.db.client import supabase

# 排除 0/O、1/I/L 這些手寫或小螢幕上容易看錯的字元
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 6
CATEGORIES = ("experiment", "tester")


def normalize_code(text: str) -> str:
    """手機輸入常會打出全形字、混大小寫、或多帶空白／連字號，統一轉成半形大寫英數。"""
    halfwidth = unicodedata.normalize("NFKC", text).upper()
    return "".join(ch for ch in halfwidth if ch.isascii() and ch.isalnum())


def _generate_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def create_codes(count: int, category: str, note: Optional[str] = None) -> list[str]:
    if category not in CATEGORIES:
        raise ValueError(f"category 必須是 {CATEGORIES} 其中之一")

    existing = {row["code"] for row in supabase.table("access_codes").select("code").execute().data}
    codes: list[str] = []
    while len(codes) < count:
        code = _generate_code()
        if code in existing or code in codes:
            continue
        codes.append(code)

    supabase.table("access_codes").insert(
        [{"code": code, "category": category, "note": note} for code in codes]
    ).execute()
    return codes


def redeem(user_id: UUID, raw_text: str) -> Optional[dict]:
    """兌換成功回傳該開通碼的資料列（含 category），失敗（格式不對、不存在、已被使用、
    已作廢）一律回傳 None，不區分原因，避免透露哪些碼存在。"""
    code = normalize_code(raw_text)
    if len(code) != CODE_LENGTH:
        return None

    rows = (
        supabase.table("access_codes")
        .update({"user_id": str(user_id), "redeemed_at": datetime.now(timezone.utc).isoformat()})
        .eq("code", code)
        .is_("user_id", "null")
        .eq("revoked", False)
        .execute()
        .data
    )
    if not rows:
        return None

    supabase.table("users").update({"status": "active"}).eq("id", str(user_id)).eq("status", "pending").execute()
    return rows[0]
