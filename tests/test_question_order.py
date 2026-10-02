"""出題順序：単語／言語知識在同一輪內隨機出題，諺依題號順序。不論哪種順序，本輪答過的題號
都不會再出現。"""

import uuid

from app.db.client import supabase
from app.services.question_picker import get_available_questions_in_scope

from .conftest import (
    cleanup_test_data,
    insert_language_knowledge_questions,
    insert_proverb_questions,
    insert_vocab_questions,
    make_exam_scope,
)


def _first_numbers(mode: str, exam_scope: str, user_id: str, tries: int = 30) -> set[int]:
    return {
        get_available_questions_in_scope(user_id, mode, exam_scope, 1, limit=1)[0]["question_number"]
        for _ in range(tries)
    }


def test_vocab_and_language_knowledge_are_random_proverb_is_sequential():
    nobody = str(uuid.uuid4())  # 沒有任何作答紀錄的使用者 id，只用來查詢，不寫入
    vocab_scope, lk_scope, proverb_scope = make_exam_scope("v_order"), make_exam_scope("lk_order"), make_exam_scope("p_order")
    vocab = insert_vocab_questions(vocab_scope, count=8)
    lk = insert_language_knowledge_questions(lk_scope, count=8)
    proverbs = insert_proverb_questions(proverb_scope, count=4)
    try:
        # 8 題抽 30 次，第一題若是依序就永遠是 1；隨機的話幾乎不可能 30 次都一樣
        assert len(_first_numbers("vocab", vocab_scope, nobody)) > 1
        assert len(_first_numbers("language_knowledge", lk_scope, nobody)) > 1
        assert _first_numbers("proverb", proverb_scope, nobody) == {1}
    finally:
        supabase.table("questions").delete().eq("exam_scope", vocab_scope).execute()
        supabase.table("questions").delete().eq("exam_scope", lk_scope).execute()
        supabase.table("questions").delete().eq("exam_scope", proverb_scope).execute()


def test_random_order_never_repeats_attempted_questions(test_user):
    from app.services.answer_handler import finalize_attempt

    exam_scope = make_exam_scope("v_norepeat")
    questions = insert_vocab_questions(exam_scope, count=5)
    ids = [q["id"] for q in questions]
    try:
        seen = []
        for _ in range(5):
            q = get_available_questions_in_scope(test_user, "vocab", exam_scope, 1, limit=1)[0]
            assert q["question_number"] not in seen
            seen.append(q["question_number"])
            finalize_attempt(user_id=test_user, question=q, is_correct=True, selected_option="a")
        assert sorted(seen) == [1, 2, 3, 4, 5]
        assert get_available_questions_in_scope(test_user, "vocab", exam_scope, 1, limit=1) == []
    finally:
        cleanup_test_data(test_user, "vocab", exam_scope, ids)
