"""
手動備份腳本：把資料庫每張表的內容匯出成 JSON 檔案。

免費方案的 Supabase 沒有自動備份，這支腳本提供一個不需要額外安裝任何工具（不需要
Docker、不需要 pg_dump）的備份方式——直接用專案已經在用的 Supabase Python client
把每張表的資料讀出來存成 JSON。真的需要復原時，流程是：先用 app/db/schema.sql
建好表結構，再把這裡備份的 JSON 資料一筆一筆灌回去（或用 supabase-py 的 insert）。

這不是完整的 SQL dump（不含 sequence、function、trigger 等，這個專案目前也沒有用到
這些），但涵蓋了所有實際的資料列，對於「資料被誤刪／改壞時能救回來」這個目的已經足夠。

用法：
    python scripts/backup_database.py
    python scripts/backup_database.py --out-dir backups

會在 backups/ 底下建立一個以時間戳記命名的資料夾，每張表各自一個 JSON 檔案。
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.client import supabase  # noqa: E402

TABLES = [
    "users",
    "questions",
    "attempts_log",
    "wrong_question_state",
    "scope_progress",
    "active_exam_scope",
    "daily_challenge",
    "ai_conversation_usage",
    "feedback_logs",
    "menu_interaction_log",
    "user_session_state",
    "ai_conversation_log",
    "push_log",
]

PAGE_SIZE = 1000


def dump_table(table: str) -> list[dict]:
    """分頁抓取整張表的資料，避免超過 API 單次回傳筆數上限時漏資料。"""
    rows: list[dict] = []
    offset = 0
    while True:
        page = supabase.table(table).select("*").range(offset, offset + PAGE_SIZE - 1).execute().data
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="備份資料庫每張表為 JSON 檔案")
    parser.add_argument("--out-dir", default="backups", help="備份存放的根目錄（預設 backups/）")
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir) / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    for table in TABLES:
        rows = dump_table(table)
        (out_dir / f"{table}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        print(f"  {table}: {len(rows)} 筆")
        total_rows += len(rows)

    print(f"備份完成：{out_dir}（共 {total_rows} 筆，跨 {len(TABLES)} 張表）")


if __name__ == "__main__":
    main()
