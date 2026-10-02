"""開通碼兌換的測試。直接對正式 Supabase 跑：碼都標記 note='pytest'，使用者是隨機
line_user_id 的測試帳號，結束後（不論成功失敗）全部清除。"""

import threading
import uuid

import pytest

from app.db.client import supabase
from app.services.access_codes import create_codes, normalize_code, redeem


def _make_user() -> str:
    return supabase.table("users").insert({"line_user_id": f"pytest_{uuid.uuid4().hex[:16]}"}).execute().data[0]["id"]


def _status(user_id: str) -> str:
    return supabase.table("users").select("status").eq("id", user_id).execute().data[0]["status"]


@pytest.fixture
def cleanup():
    codes: list[str] = []
    users: list[str] = []
    yield codes, users
    if codes:
        supabase.table("access_codes").delete().in_("code", codes).execute()
    if users:
        supabase.table("users").delete().in_("id", users).execute()


def test_normalize_code():
    assert normalize_code("k7p2qx") == "K7P2QX"
    assert normalize_code(" K7P-2QX \n") == "K7P2QX"
    assert normalize_code("Ｋ７Ｐ２ＱＸ") == "K7P2QX"  # 手機全形輸入
    assert normalize_code("開通碼：k7 p2 qx") == "K7P2QX"


def test_redeem_activates_pending_user_and_binds_code(cleanup):
    codes, users = cleanup
    code = create_codes(1, "tester", note="pytest")[0]
    codes.append(code)
    user = _make_user()
    users.append(user)
    assert _status(user) == "pending"

    # 用全形＋小寫輸入，確認正規化後一樣能兌換
    fullwidth_lower = code.lower().translate({ord(c): ord(c) + 0xFEE0 for c in code.lower()})
    row = redeem(user, fullwidth_lower)

    assert row is not None and row["category"] == "tester"
    assert _status(user) == "active"
    bound = supabase.table("access_codes").select("user_id, redeemed_at").eq("code", code).execute().data[0]
    assert bound["user_id"] == user and bound["redeemed_at"] is not None


def test_code_cannot_be_reused(cleanup):
    codes, users = cleanup
    code = create_codes(1, "tester", note="pytest")[0]
    codes.append(code)
    first, second = _make_user(), _make_user()
    users.extend([first, second])

    assert redeem(first, code) is not None
    assert redeem(second, code) is None
    assert _status(second) == "pending"


def test_revoked_and_unknown_codes_rejected(cleanup):
    codes, users = cleanup
    code = create_codes(1, "tester", note="pytest")[0]
    codes.append(code)
    supabase.table("access_codes").update({"revoked": True}).eq("code", code).execute()
    user = _make_user()
    users.append(user)

    assert redeem(user, code) is None
    assert redeem(user, "ZZZZZZ") is None  # 不存在
    assert redeem(user, "你好") is None  # 一般聊天文字
    assert _status(user) == "pending"


def test_concurrent_redeem_only_one_wins(cleanup):
    codes, users = cleanup
    code = create_codes(1, "tester", note="pytest")[0]
    codes.append(code)
    contenders = [_make_user() for _ in range(5)]
    users.extend(contenders)

    results: list = [None] * len(contenders)

    def attempt(i: int) -> None:
        results[i] = redeem(contenders[i], code)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(len(contenders))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(r is not None for r in results) == 1
    assert sum(_status(u) == "active" for u in contenders) == 1
