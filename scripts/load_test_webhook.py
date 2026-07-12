"""
針對正式環境的併發負載測試：模擬多位使用者同時觸發「下一題」動作，量測正式環境
在真實併發流量下的回應時間，並確認不會出現非預期的錯誤。

背景：課堂上老師會請全班（約 30-40 人）當場加好友並開始使用，這會在短時間內對
webhook 端點造成真實的併發流量。Phase 8 做過的併發測試驗證的是「多執行緒下不會
互相干擾」（抓到過 HTTP/2 client 共用的 bug），但沒有模擬過這個規模。這支腳本直接
對正式環境送出模擬流量，用假的 line_user_id（不是真實學生），量測結果後把這些
假使用者留下的資料列清乾淨。

注意：這裡送出的 reply_token 是假的（LINE 只在真正的 webhook 事件裡核發），所以
每個請求最後嘗試呼叫 LINE Reply API 時一定會失敗——這是預期內、無害的（程式碼裡
有 _fallback_reply 兜底，失敗只會記錄不會讓請求整個掛掉），我們真正要看的是「在
這個併發規模下，close整個 webhook 處理流程（DB 讀寫＋業務邏輯）本身要花多久」，
不是 LINE 那端的回覆是否成功。

用法：
    python scripts/load_test_webhook.py --concurrency 35 --url https://hibi-bot-production.up.railway.app/webhook
"""

import argparse
import base64
import hashlib
import hmac
import json
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.db.client import supabase  # noqa: E402

LINE_USER_ID_PREFIX = "loadtest-"


def _sign(body: bytes) -> str:
    digest = hmac.new(settings.line_channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _build_payload(line_user_id: str) -> bytes:
    event = {
        "type": "postback",
        "replyToken": f"loadtest-fake-token-{uuid.uuid4()}",
        "source": {"type": "user", "userId": line_user_id},
        "timestamp": int(time.time() * 1000),
        "mode": "active",
        "postback": {"data": "action=next_question&mode=vocab"},
        "webhookEventId": f"loadtest-{uuid.uuid4()}",
        "deliveryContext": {"isRedelivery": False},
    }
    return json.dumps({"events": [event]}).encode("utf-8")


def _fire_one(url: str, line_user_id: str) -> dict:
    body = _build_payload(line_user_id)
    signature = _sign(body)
    started = time.monotonic()
    try:
        resp = httpx.post(
            url,
            content=body,
            headers={"Content-Type": "application/json", "X-Line-Signature": signature},
            timeout=30.0,
        )
        elapsed = time.monotonic() - started
        return {"line_user_id": line_user_id, "status": resp.status_code, "elapsed": elapsed, "error": None}
    except Exception as e:
        elapsed = time.monotonic() - started
        return {"line_user_id": line_user_id, "status": None, "elapsed": elapsed, "error": str(e)}


def cleanup(line_user_ids: list[str]) -> None:
    print("\n清理測試資料...")
    users = (
        supabase.table("users")
        .select("id, line_user_id")
        .in_("line_user_id", line_user_ids)
        .execute()
        .data
    )
    user_ids = [u["id"] for u in users]
    if not user_ids:
        print("  沒有建立任何使用者資料列（可能所有請求都在建立使用者前就失敗了）")
        return

    for table in [
        "attempts_log",
        "wrong_question_state",
        "scope_progress",
        "menu_interaction_log",
        "user_session_state",
        "daily_challenge",
        "ai_conversation_log",
        "ai_conversation_usage",
    ]:
        supabase.table(table).delete().in_("user_id", user_ids).execute()
    supabase.table("users").delete().in_("id", user_ids).execute()
    print(f"  已清除 {len(user_ids)} 位假使用者及其關聯資料列")


def main() -> None:
    parser = argparse.ArgumentParser(description="對正式環境 webhook 做併發負載測試")
    parser.add_argument("--concurrency", type=int, default=35, help="模擬同時觸發的使用者數（預設 35）")
    parser.add_argument("--url", required=True, help="正式環境 webhook 端點網址")
    args = parser.parse_args()

    line_user_ids = [f"{LINE_USER_ID_PREFIX}{uuid.uuid4()}" for _ in range(args.concurrency)]

    print(f"對 {args.url} 送出 {args.concurrency} 個併發請求...")
    overall_start = time.monotonic()
    results = []
    try:
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = [executor.submit(_fire_one, args.url, uid) for uid in line_user_ids]
            for future in as_completed(futures):
                results.append(future.result())
        overall_elapsed = time.monotonic() - overall_start

        elapsed_list = [r["elapsed"] for r in results]
        ok_count = sum(1 for r in results if r["status"] == 200)
        error_results = [r for r in results if r["status"] != 200]

        print(f"\n總耗時：{overall_elapsed:.2f}s（{args.concurrency} 個請求並發送出）")
        print(f"成功（HTTP 200）：{ok_count}/{len(results)}")
        print(f"單一請求耗時：最快 {min(elapsed_list):.2f}s／最慢 {max(elapsed_list):.2f}s／平均 {sum(elapsed_list)/len(elapsed_list):.2f}s")

        if error_results:
            print(f"\n非 200 的請求（{len(error_results)} 個）：")
            for r in error_results[:10]:
                print(f"  status={r['status']} error={r['error']}")
    finally:
        cleanup(line_user_ids)


if __name__ == "__main__":
    main()
