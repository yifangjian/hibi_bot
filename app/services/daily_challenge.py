import logging
import random
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from app.db.client import supabase
from app.services import completion_card_generator, flex_templates, line_client
from app.services.answer_handler import finalize_attempt
from app.services.question_picker import get_current_scope_and_round, get_available_questions_in_scope, get_question
from app.services.session_state import set_session_state

logger = logging.getLogger("hibi_bot.daily_challenge")

MODES = ["vocab", "proverb", "language_knowledge"]
CHALLENGE_SIZE = 5


def _available_questions_for_mode(user_id: str, mode: str) -> list[dict[str, Any]]:
    """這個模式目前輪次還沒作答過的題目（依 question_number 排序），最多抓 CHALLENGE_SIZE
    筆代表列——每日挑戰單一模式最多用到這麼多題，不需要抓下整個範圍的完整內容。"""
    exam_scope, current_round = get_current_scope_and_round(user_id, mode)
    if exam_scope is None:
        return []
    return get_available_questions_in_scope(user_id, mode, exam_scope, current_round, limit=CHALLENGE_SIZE)


def generate_challenge_for_user(user_id: str, challenge_date: date) -> dict[str, Any]:
    """決定當天 5 題（或不足 5 題，若題庫已無剩餘題目）：每一格獨立隨機選一個還有
    剩餘題目的模式，依序取該模式下一題，同一天內不會重複同一題。"""
    available = {mode: _available_questions_for_mode(user_id, mode) for mode in MODES}
    cursor = {mode: 0 for mode in MODES}

    picked: list[dict[str, str]] = []
    for _ in range(CHALLENGE_SIZE):
        candidate_modes = [m for m in MODES if cursor[m] < len(available[m])]
        if not candidate_modes:
            break
        mode = random.choice(candidate_modes)
        question = available[mode][cursor[mode]]
        cursor[mode] += 1
        picked.append({"mode": mode, "question_id": question["id"]})

    row = (
        supabase.table("daily_challenge")
        .insert({"user_id": str(user_id), "challenge_date": challenge_date.isoformat(), "questions": picked})
        .execute()
        .data[0]
    )
    return row


def get_or_create_today_challenge(user_id: str) -> dict[str, Any]:
    today = date.today().isoformat()
    existing = (
        supabase.table("daily_challenge")
        .select("*")
        .eq("user_id", str(user_id))
        .eq("challenge_date", today)
        .execute()
        .data
    )
    if existing:
        return existing[0]
    return generate_challenge_for_user(user_id, date.today())


def is_expired(challenge: dict[str, Any]) -> bool:
    return challenge["challenge_date"] != date.today().isoformat()


def _progress_text(challenge: dict[str, Any]) -> str:
    total = len(challenge["questions"])
    return f"挑戰進度：{challenge['current_index'] + 1}/{total}"


def serve_current_question(user_id: UUID, challenge: dict[str, Any], reply_token: str) -> None:
    total = len(challenge["questions"])
    if challenge["completed"] or challenge["current_index"] >= total:
        line_client.reply_text(reply_token, "今天的每日挑戰已經完成囉！")
        return

    ref = challenge["questions"][challenge["current_index"]]
    question = get_question(ref["question_id"])
    if not question:
        line_client.reply_text(reply_token, "挑戰題目讀取失敗，請稍後再試。")
        return

    line_client.reply_flex(
        reply_token,
        alt_text="每日挑戰",
        contents=flex_templates.build_challenge_question_card(question, challenge["id"], _progress_text(challenge)),
    )


def start_or_resume(user_id: UUID, challenge_id: str, reply_token: str) -> None:
    rows = supabase.table("daily_challenge").select("*").eq("id", challenge_id).execute().data
    challenge = rows[0] if rows else None
    if not challenge:
        line_client.reply_text(reply_token, "找不到這個挑戰，請稍後再試。")
        return

    if is_expired(challenge):
        line_client.reply_text(reply_token, "這是之前的每日挑戰，已經結束囉。")
        return

    if challenge["completed"]:
        line_client.reply_text(reply_token, "今天的每日挑戰已經完成囉，明天再來挑戰吧！")
        return

    serve_current_question(user_id, challenge, reply_token)


def _get_line_user_id(user_id: UUID) -> str:
    row = supabase.table("users").select("line_user_id").eq("id", str(user_id)).execute().data[0]
    return row["line_user_id"]


def _handle_completion(user_id: UUID, challenge: dict[str, Any], reply_token: str) -> None:
    results = challenge["results"]
    total = len(results)
    correct_count = sum(1 for r in results if r["is_correct"])
    accuracy_pct = round(correct_count / total * 100) if total else 0

    line_user_id = _get_line_user_id(user_id)

    try:
        display_name = line_client.get_display_name(line_user_id)
    except Exception:
        logger.exception("failed to fetch LINE display name, using fallback")
        display_name = "同學"

    image_url = completion_card_generator.generate_completion_image(
        display_name=display_name,
        accuracy_pct=accuracy_pct,
        date_str=challenge["challenge_date"],
    )

    line_client.reply_image(reply_token, image_url)
    line_client.switch_rich_menu_to_main(line_user_id)


def record_answer(user_id: UUID, challenge_id: str, question_id: str, is_correct: bool, reply_token: str) -> None:
    """紀錄這一題挑戰結果，推進到下一題或觸發完成流程。"""
    rows = supabase.table("daily_challenge").select("*").eq("id", challenge_id).execute().data
    challenge = rows[0] if rows else None
    if not challenge:
        line_client.reply_text(reply_token, "找不到這個挑戰，請稍後再試。")
        return

    results = challenge["results"] + [{"question_id": question_id, "is_correct": is_correct}]
    new_index = challenge["current_index"] + 1
    completed = new_index >= len(challenge["questions"])

    update_payload: dict[str, Any] = {"results": results, "current_index": new_index}
    if completed:
        update_payload["completed"] = True
        update_payload["completed_at"] = datetime.now(timezone.utc).isoformat()

    updated = supabase.table("daily_challenge").update(update_payload).eq("id", challenge_id).execute().data[0]

    if completed:
        _handle_completion(user_id, updated, reply_token)
    else:
        serve_current_question(user_id, updated, reply_token)


def handle_challenge_answer(user_id: UUID, params: dict, reply_token: str) -> None:
    challenge_id = params.get("challenge_id")
    qid = params.get("qid")
    opt = params.get("opt")

    rows = supabase.table("daily_challenge").select("*").eq("id", challenge_id).execute().data
    challenge = rows[0] if rows else None
    if not challenge:
        line_client.reply_text(reply_token, "找不到這個挑戰，請稍後再試。")
        return
    if is_expired(challenge):
        line_client.reply_text(reply_token, "這是之前的每日挑戰，已經結束囉。")
        return

    question = get_question(qid)
    if not question:
        line_client.reply_text(reply_token, "找不到這一題，請重新開始挑戰。")
        return

    is_correct = opt == question.get("correct_option")

    if question["mode"] == "proverb" and question.get("stage") in ("semantic_choice", "situational_choice"):
        # 諺第一階段：先記錄選擇，轉入讀音輸入階段，尚未寫入 attempts_log／daily_challenge
        set_session_state(
            user_id,
            "awaiting_reading_input",
            {
                "question_id": question["id"],
                "mode": "proverb",
                "stage1_option": opt,
                "stage1_correct": is_correct,
                "challenge_id": challenge_id,
            },
        )
        line_client.reply_flex(
            reply_token,
            alt_text="請輸入讀音",
            contents=flex_templates.build_reading_input_prompt_card(question),
        )
        return

    # 単語 / 言語知識：單階段，直接判定、寫入，並推進挑戰進度
    finalize_attempt(
        user_id=user_id,
        question=question,
        is_correct=is_correct,
        selected_option=opt,
        daily_challenge_id=challenge_id,
    )
    record_answer(user_id, challenge_id, question["id"], is_correct, reply_token)


def run_daily_push() -> dict[str, Any]:
    """Cron 進入點：為每位使用者產生今日挑戰並推播「開始挑戰」卡片。每位使用者獨立
    try/except——單一使用者的資料異常或推播失敗（例如已封鎖官方帳號）不該讓迴圈中斷、
    連累當天排在後面的其他使用者完全收不到推播。
    """
    users = supabase.table("users").select("id, line_user_id").execute().data
    today = date.today()

    pushed = 0
    skipped = 0
    failed = 0
    for user in users:
        user_id = user["id"]
        line_user_id = user["line_user_id"]

        try:
            existing = (
                supabase.table("daily_challenge")
                .select("id")
                .eq("user_id", user_id)
                .eq("challenge_date", today.isoformat())
                .execute()
                .data
            )
            if existing:
                # 理論上 cron 一天只會觸發一次，這裡應該永遠不會命中；保留是為了不小心
                # 重複觸發時（手動重跑、cron 意外觸發兩次）不要對已經有今日挑戰的使用者
                # 重複推播，也不要把「本來就有」誤判成「失敗」。
                logger.info("user=%s already has today's challenge, skip push", user_id)
                skipped += 1
                continue

            challenge = generate_challenge_for_user(user_id, today)
            if not challenge["questions"]:
                logger.info("user=%s has no available questions today, skip push", user_id)
                skipped += 1
                continue

            line_client.push_flex(
                line_user_id,
                alt_text="每日挑戰",
                contents=flex_templates.build_daily_challenge_start_card(challenge["id"]),
            )
            supabase.table("push_log").insert({"user_id": user_id, "challenge_id": challenge["id"]}).execute()
            pushed += 1
        except Exception:
            logger.exception("Failed to push daily challenge to user=%s", user_id)
            failed += 1

    return {"users": len(users), "pushed": pushed, "skipped": skipped, "failed": failed}
