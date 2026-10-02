"""
作廢一組開通碼；若已經有人用這組碼開通，連同該使用者一起停用（status → inactive）。

用途：碼外流被不該用的人兌換、或同學換了 LINE 帳號需要重發。換帳號的情況，作廢舊碼後
再發一組新碼給同學在新帳號輸入即可。只改狀態，不刪除任何作答紀錄。

用法：
    python scripts/revoke_access_code.py --code K7P2QX
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.client import supabase  # noqa: E402
from app.services.access_codes import normalize_code  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="作廢開通碼")
    parser.add_argument("--code", required=True)
    args = parser.parse_args()

    code = normalize_code(args.code)
    rows = supabase.table("access_codes").select("*").eq("code", code).execute().data
    if not rows:
        print(f"找不到開通碼 {code}")
        sys.exit(1)

    row = rows[0]
    supabase.table("access_codes").update({"revoked": True}).eq("code", code).execute()
    print(f"已作廢開通碼 {code}（{row['category']}）")

    if row["user_id"]:
        supabase.table("users").update({"status": "inactive"}).eq("id", row["user_id"]).execute()
        print(f"綁定的使用者 {row['user_id']} 已一併停用")


if __name__ == "__main__":
    main()
