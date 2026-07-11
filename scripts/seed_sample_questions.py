"""
灌入最小的測試題庫，供端到端測試使用（単語 x2、言語知識 x2、諺 x1 句 3 筆）。
每個 mode 內的 question_number 從 1 開始流水編號，供 AI 助教依題號查詢。
諺同一句用同一個 question_number，semantic_choice/situational_choice/reading_input
各一筆（見 scripts/import_proverb_questions.py 說明）。
所有題目都放在 exam_scope="1"，並把它設為每個 mode 目前的 active_exam_scope。

    python scripts/seed_sample_questions.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.client import supabase  # noqa: E402


def insert(row: dict) -> dict:
    return supabase.table("questions").insert(row).execute().data[0]


def main() -> None:
    insert(
        {
            "mode": "vocab",
            "exam_scope": "1",
            "question_number": 1,
            "context_sentence": "彼は毎朝＿＿＿を読んでから出勤する。",
            "blank_marker": "＿＿＿",
            "options": [
                {"id": "a", "text": "しんぶん"},
                {"id": "b", "text": "しんふん"},
                {"id": "c", "text": "しいぶん"},
            ],
            "correct_option": "a",
            "explanation_rule": "「新聞」は音読みで「しんぶん」と読む。連濁に注意。",
        }
    )
    insert(
        {
            "mode": "vocab",
            "exam_scope": "1",
            "question_number": 2,
            "context_sentence": "この＿＿＿はとても静かで勉強に集中できる。",
            "blank_marker": "＿＿＿",
            "options": [
                {"id": "a", "text": "としょかん"},
                {"id": "b", "text": "としょうかん"},
                {"id": "c", "text": "とうしょかん"},
            ],
            "correct_option": "a",
            "explanation_rule": "「図書館」は「としょかん」。長音の位置に注意。",
        }
    )

    insert(
        {
            "mode": "language_knowledge",
            "exam_scope": "1",
            "question_number": 1,
            "context_sentence": "彼の説明は＿＿＿要領を得ない。",
            "blank_marker": "＿＿＿",
            "options": [
                {"id": "a", "text": "いかにも"},
                {"id": "b", "text": "どうも"},
                {"id": "c", "text": "さも"},
            ],
            "correct_option": "b",
            "explanation_rule": "「どうも要領を得ない」は定型表現で、はっきりしない様子を表す。",
        }
    )
    insert(
        {
            "mode": "language_knowledge",
            "exam_scope": "1",
            "question_number": 2,
            "context_sentence": "彼女は＿＿＿の努力の末、試験に合格した。",
            "blank_marker": "＿＿＿",
            "options": [
                {"id": "a", "text": "並々ならぬ"},
                {"id": "b", "text": "何気ない"},
                {"id": "c", "text": "たわいない"},
            ],
            "correct_option": "a",
            "explanation_rule": "「並々ならぬ努力」で「並外れた、普通ではない努力」を表す。",
        }
    )

    # 諺：同一句（question_number=1）匯入 3 筆，semantic_choice/situational_choice 出題時隨機擇一，
    # reading_input 一律接在第二階段。三筆共用同一個 question_number，不再用 parent_question_id 關聯。
    insert(
        {
            "mode": "proverb",
            "exam_scope": "1",
            "question_number": 1,
            "stage": "semantic_choice",
            "context_sentence": "「七転び八起き」の意味として、最も適切なものはどれか。",
            "blank_marker": None,
            "options": [
                {"id": "a", "text": "何度失敗しても諦めずに立ち上がる様子"},
                {"id": "b", "text": "一度の失敗で完全に諦めてしまう様子"},
                {"id": "c", "text": "他人の失敗を笑う様子"},
            ],
            "correct_option": "a",
            "explanation_rule": "「七転び八起き」は何度失敗しても諦めずに立ち上がる様子を表すことわざ。",
        }
    )
    insert(
        {
            "mode": "proverb",
            "exam_scope": "1",
            "question_number": 1,
            "stage": "situational_choice",
            "context_sentence": "何度も失敗しても諦めずに挑戦し続ける友人を見て、「＿＿＿」と励ました。",
            "blank_marker": "＿＿＿",
            "options": [
                {"id": "a", "text": "七転び八起き"},
                {"id": "b", "text": "猿も木から落ちる"},
                {"id": "c", "text": "花より団子"},
            ],
            "correct_option": "a",
            "explanation_rule": "「七転び八起き」は何度失敗しても諦めずに立ち上がる様子を表すことわざ。",
        }
    )
    insert(
        {
            "mode": "proverb",
            "exam_scope": "1",
            "question_number": 1,
            "stage": "reading_input",
            "context_sentence": None,
            "blank_marker": None,
            "options": None,
            "correct_option": "ななころびやおき",
            "explanation_rule": "「七転び八起き」の読みは「ななころびやおき」。",
        }
    )

    for mode in ["vocab", "proverb", "language_knowledge"]:
        supabase.table("active_exam_scope").upsert({"mode": mode, "exam_scope": "1"}).execute()

    print("已灌入測試題庫：単語 x2、言語知識 x2、諺 x1 句（3 列），並將三個模式的 active_exam_scope 設為 \"1\"")


if __name__ == "__main__":
    main()
