"""
匯入單字題庫，支援兩種格式（依工作表名稱自動判斷）：

- 「文脈穴埋め」（115 學年起）：情境句挖空（___），選出空格中詞語的讀音或寫法，每題附解析
  （【単語】【読み】【意味】【例文】【中文】…），答題後跟諺／言語知識一樣由 AI 依解析生成說明。
- 「読み方クイズ」（前測／暑修班）：題目是單一詞彙、選讀音、沒有解析，答題後只顯示正確讀音，
  不呼叫 OpenAI（見 app/services/feedback_generator.py 的 _has_no_explanation）。

question_number 從 1 開始流水編號，只在同一個 (mode, exam_scope) 內唯一（見
app/db/schema.sql 的 unique_question_number_per_scope_stage）。

重複使用注意事項（跟 import_proverb_questions.py 相同）：
- 這是「全量匯入」腳本，不是增量／upsert。執行前會先檢查指定的 exam_scope 底下是否
  已經有 vocab 題目，如果有就直接中止，不會自動覆蓋或疊加。
- 換到全新的考試範圍：直接換一個新的 --exam-scope 字串即可。匯入後記得手動更新
  active_exam_scope 切到新範圍。
- 要修正/更新已匯入的內容：這支腳本不會做任何刪除，需要手動決定是否清除舊資料，
  動手前務必先查 attempts_log/wrong_question_state 有沒有已經參照這些題目的作答紀錄。

用法：
    # 先跑小批次（前 5 個詞）確認流程沒問題
    python scripts/import_vocab_questions.py \\
        --file "data/raw/日語讀音測驗_270題.xlsx" \\
        --exam-scope "高日暑修班期中考" --limit 5

    # 確認沒問題後，正式全量匯入
    python scripts/import_vocab_questions.py \\
        --file "data/raw/日語讀音測驗_270題.xlsx" \\
        --exam-scope "高日暑修班期中考"
"""

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl  # noqa: E402

from app.db.client import supabase  # noqa: E402

SHEET_NAME = "読み方クイズ"  # 前測（暑修班）格式：單一詞彙、選讀音、沒有解析
SHEET_CONTEXT = "文脈穴埋め"  # 115 學年起的格式：情境句挖空、選讀音或寫法、每題附解析
BLANK_MARKER = "___"
OPTION_LETTERS = ["A", "B", "C", "D"]


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _read_rows(ws) -> list[dict[str, Any]]:
    rows = []
    for r in range(2, ws.max_row + 1):
        word = ws.cell(row=r, column=1).value
        if word is None or _clean(word) == "":
            break
        options = [
            {"id": letter.lower(), "text": _clean(ws.cell(row=r, column=2 + i).value)}
            for i, letter in enumerate(OPTION_LETTERS)
        ]
        correct_answer = _clean(ws.cell(row=r, column=6).value).upper()
        rows.append({"word": _clean(word), "options": options, "correct_option": correct_answer.lower()})
    return rows


def _read_context_rows(ws) -> list[dict[str, Any]]:
    """文脈穴埋め 格式：題目（情境句，含 ___ 挖空）／選項A-D／正確答案／解析。"""
    rows = []
    for r in range(2, ws.max_row + 1):
        sentence = ws.cell(row=r, column=1).value
        if sentence is None or _clean(sentence) == "":
            break
        sentence = _clean(sentence)
        options = [
            {"id": letter.lower(), "text": _clean(ws.cell(row=r, column=2 + i).value)}
            for i, letter in enumerate(OPTION_LETTERS)
        ]
        rows.append(
            {
                "word": sentence,
                "blank_marker": BLANK_MARKER if BLANK_MARKER in sentence else None,
                "options": options,
                "correct_option": _clean(ws.cell(row=r, column=6).value).lower(),
                "explanation_rule": _clean(ws.cell(row=r, column=7).value) or None,
            }
        )
    return rows


def build_rows(entries: list[dict[str, Any]], exam_scope: str) -> list[dict[str, Any]]:
    return [
        {
            "mode": "vocab",
            "exam_scope": exam_scope,
            "question_number": i,
            "stage": None,
            "context_sentence": entry["word"],
            "blank_marker": entry.get("blank_marker"),
            "options": entry["options"],
            "correct_option": entry["correct_option"],
            "explanation_rule": entry.get("explanation_rule"),
        }
        for i, entry in enumerate(entries, start=1)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="匯入單字讀音題庫（読み方クイズ）")
    parser.add_argument("--file", required=True, help="Excel 檔案路徑（相對於專案根目錄）")
    parser.add_argument("--exam-scope", required=True, help="這批題目要匯入的 exam_scope 標籤")
    parser.add_argument("--limit", type=int, default=None, help="只匯入前 N 個詞（測試用）")
    parser.add_argument("--dry-run", action="store_true", help="只讀檔並顯示結果，不寫入資料庫")
    args = parser.parse_args()

    existing = (
        supabase.table("questions").select("id").eq("mode", "vocab").eq("exam_scope", args.exam_scope).execute()
    )
    if existing.data:
        print(f'錯誤：exam_scope="{args.exam_scope}" 底下已經有 {len(existing.data)} 筆 vocab 題目，中止匯入。')
        print("如果是要修正/更新這個範圍的題庫，請先手動確認並清除舊資料（注意 attempts_log 等表格的參照）。")
        sys.exit(1)

    wb = openpyxl.load_workbook(args.file, data_only=True)
    if SHEET_CONTEXT in wb.sheetnames:
        entries = _read_context_rows(wb[SHEET_CONTEXT])
    else:
        entries = _read_rows(wb[SHEET_NAME])

    rows = build_rows(entries, args.exam_scope)
    if args.limit:
        rows = rows[: args.limit]

    if args.dry_run:
        with_expl = sum(1 for r in rows if r["explanation_rule"])
        print(f"[dry-run] 讀到 {len(rows)} 題（{with_expl} 題有解析），未寫入資料庫")
        return

    # 分批寫入，避免逐筆寫幾百次中途斷線留下匯到一半的資料
    for start in range(0, len(rows), 100):
        supabase.table("questions").insert(rows[start : start + 100]).execute()

    print(f'已匯入 {len(rows)} 個單字，exam_scope="{args.exam_scope}"')


if __name__ == "__main__":
    main()
