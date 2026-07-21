"""
審核通過一位 pending 的使用者：把 status 改成 active，並推播一則歡迎訊息通知本人。

用途：新使用者第一次互動時，狀態預設是 pending，系統會寄 email 通知研究者；研究者
對照問卷填答名單確認資格後，用這支腳本正式開通。

用法：
    python scripts/approve_user.py --line-user-id U1234567890abcdef1234567890abcdef
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.client import supabase  # noqa: E402
from app.services import line_client  # noqa: E402

WELCOME_MESSAGE = "您好，您的帳號已通過審核，現在可以正式開始使用囉！點選下方選單開始練習吧 🎉"


def main() -> None:
    parser = argparse.ArgumentParser(description="審核通過一位 pending 使用者")
    parser.add_argument("--line-user-id", required=True, help="要開通的 line_user_id")
    args = parser.parse_args()

    rows = supabase.table("users").select("id, status").eq("line_user_id", args.line_user_id).execute().data
    if not rows:
        print(f"找不到 line_user_id={args.line_user_id} 的使用者")
        sys.exit(1)

    user = rows[0]
    if user["status"] == "active":
        print("這位使用者本來就已經是 active 狀態，不需要重複開通。")
        sys.exit(0)

    try:
        display_name = line_client.get_display_name(args.line_user_id)
    except Exception:
        display_name = "（查詢顯示名稱失敗）"

    supabase.table("users").update({"status": "active"}).eq("id", user["id"]).execute()
    line_client.push_text(args.line_user_id, WELCOME_MESSAGE)

    print(f"已開通：{display_name}（line_user_id={args.line_user_id}），並推播歡迎訊息。")


if __name__ == "__main__":
    main()
