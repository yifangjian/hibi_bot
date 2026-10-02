"""
產生一批開通碼並輸出成 CSV。

資料庫只存開通碼本身跟綁定的 LINE 帳號，不存學號／姓名。CSV 多留了「學號」「姓名」兩個
空白欄位讓研究者自己填，之後比對問卷就用學號對應開通碼、開通碼對應 user_id，不需要再靠
LINE 顯示名稱。CSV 含個資，輸出在 access_codes/（已 gitignore），絕對不能進公開 repo。

用法：
    python scripts/generate_access_codes.py --count 40 --category experiment
    python scripts/generate_access_codes.py --count 5 --category tester --note "內部測試"
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.access_codes import CATEGORIES, create_codes  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "access_codes"


def main() -> None:
    parser = argparse.ArgumentParser(description="產生開通碼")
    parser.add_argument("--count", type=int, required=True, help="要產生幾組")
    parser.add_argument("--category", required=True, choices=CATEGORIES, help="experiment（實驗組）或 tester（測試人員）")
    parser.add_argument("--note", default=None, help="選填備註，會存進資料庫（不要填學號或姓名）")
    args = parser.parse_args()

    codes = create_codes(args.count, args.category, args.note)

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / f"{args.category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    # utf-8-sig：讓 Excel 直接打開也能正確顯示中文欄位名稱
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["開通碼", "類別", "學號", "姓名"])
        for code in codes:
            writer.writerow([code, args.category, "", ""])

    print(f"已產生 {len(codes)} 組 {args.category} 開通碼，CSV：{out_path}")
    for code in codes:
        print(f"  {code}")


if __name__ == "__main__":
    main()
