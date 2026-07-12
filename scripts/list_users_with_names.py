"""
列出目前所有註冊使用者，並即時透過 LINE API 查詢每個人目前的顯示名稱。

用途：資料庫本身只存 line_user_id（LINE 內部的技術 ID），沒有存顯示名稱。當只知道
某些人的 LINE 暱稱（例如指導老師、非介入組同學）、需要判斷該不該把他們的資料排除在
正式研究資料之外時，用這支腳本對照。

用法：
    python scripts/list_users_with_names.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.client import supabase  # noqa: E402
from app.services import line_client  # noqa: E402


def main() -> None:
    users = supabase.table("users").select("id, line_user_id, created_at").order("created_at").execute().data

    print(f"共 {len(users)} 位註冊使用者：\n")
    for user in users:
        try:
            display_name = line_client.get_display_name(user["line_user_id"])
        except Exception as e:
            display_name = f"（查詢失敗：{e}）"
        print(f"顯示名稱：{display_name}")
        print(f"  user_id      : {user['id']}")
        print(f"  line_user_id : {user['line_user_id']}")
        print(f"  註冊時間     : {user['created_at']}")
        print()


if __name__ == "__main__":
    main()
