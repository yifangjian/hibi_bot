from datetime import date
from uuid import UUID

from app.config import settings
from app.db.client import supabase
from app.services import flex_templates, line_client
from app.services.ai_client import chat_completion
from app.services.question_picker import find_question_by_number, option_text
from app.services.session_state import set_session_state

TUTOR_INITIAL_SYSTEM_PROMPT = """你是一套日語教學系統的 AI 助教，正在為學習者解析他指定的某一題。

嚴格限制（必須遵守）：
- 你只能依據使用者訊息中提供的題目情境、選項、正確答案與「解釋依據」來說明，不可以引入解釋依據沒有提到的額外文法規則或知識。
- 因為使用者是主動來問的，可以比一般回饋更詳細一些，但仍不能超出這一題的範圍自由發揮。
- 使用繁體中文回覆，語氣像老師耐心解答。
- 回覆會直接顯示在 LINE 聊天室裡，LINE 不會渲染 markdown，所以絕對不要使用任何 markdown 語法（例如 **粗體**、# 標題、- 或 * 條列符號），只能用一般文字與換行。"""

TUTOR_FOLLOWUP_SYSTEM_PROMPT = """你是一套日語教學系統的 AI 助教，正在跟學習者針對某一題進行追問對話。

嚴格限制（必須遵守）：
- 你的回答必須始終聚焦在這一題的語境與其「解釋依據」範圍內，不可以引入解釋依據沒有提到的額外文法規則或知識。
- 不可以被當作通用聊天機器人使用；若使用者的問題明顯偏離這一題的範圍，禮貌地把話題導回這一題。
- 使用繁體中文回覆，語氣像老師耐心解答。
- 回覆會直接顯示在 LINE 聊天室裡，LINE 不會渲染 markdown，所以絕對不要使用任何 markdown 語法（例如 **粗體**、# 標題、- 或 * 條列符號），只能用一般文字與換行。"""


def _log(user_id: UUID, question_id: str, role: str, message: str) -> None:
    supabase.table("ai_conversation_log").insert(
        {"user_id": str(user_id), "question_id": question_id, "role": role, "message": message}
    ).execute()


def start_conversation(user_id: UUID, mode: str, question_number_text: str, reply_token: str) -> None:
    question = find_question_by_number(mode, int(question_number_text))
    if not question:
        line_client.reply_text(reply_token, "找不到這個題號，請確認輸入正確")
        return

    correct_text = option_text(question, question.get("correct_option"))
    user_content = (
        f"題目情境：{question.get('context_sentence') or ''}\n"
        f"正確答案：{correct_text}\n"
        f"解釋依據：{question.get('explanation_rule') or ''}\n"
        "請幫我解析這一題。"
    )
    messages = [
        {"role": "system", "content": TUTOR_INITIAL_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    answer = chat_completion(messages)

    _log(user_id, question["id"], "user", question_number_text)
    _log(user_id, question["id"], "assistant", answer)

    set_session_state(user_id, "in_ai_tutor_conversation", {"question_id": question["id"], "mode": mode})
    line_client.reply_flex(
        reply_token,
        alt_text="AI 助教解析",
        contents=flex_templates.build_ai_tutor_reply_card(
            answer, mode, "（初次解析不計入每日額度；還有問題可以直接打字繼續問我）"
        ),
    )


def continue_conversation(user_id: UUID, context: dict, text: str, reply_token: str) -> None:
    question_id = context["question_id"]
    mode = context["mode"]
    today = date.today().isoformat()

    usage = (
        supabase.table("ai_conversation_usage")
        .select("turn_count")
        .eq("user_id", str(user_id))
        .eq("usage_date", today)
        .execute()
    )
    turn_count = usage.data[0]["turn_count"] if usage.data else 0

    if turn_count >= settings.ai_tutor_daily_turn_limit:
        line_client.reply_flex(
            reply_token,
            alt_text="今日額度已用完",
            contents=flex_templates.build_ai_tutor_reply_card(
                "今日 AI 助教對話次數已達上限，明天再繼續問我吧", mode
            ),
        )
        return

    question = supabase.table("questions").select("*").eq("id", question_id).execute().data[0]

    history = (
        supabase.table("ai_conversation_log")
        .select("role, message")
        .eq("user_id", str(user_id))
        .eq("question_id", question_id)
        .order("created_at")
        .execute()
        .data
    )

    messages = [
        {
            "role": "system",
            "content": TUTOR_FOLLOWUP_SYSTEM_PROMPT + f"\n\n這一題的解釋依據：{question.get('explanation_rule') or ''}",
        }
    ]
    for row in history:
        messages.append({"role": row["role"], "content": row["message"]})
    messages.append({"role": "user", "content": text})

    answer = chat_completion(messages)

    _log(user_id, question_id, "user", text)
    _log(user_id, question_id, "assistant", answer)

    new_turn_count = turn_count + 1
    supabase.table("ai_conversation_usage").upsert(
        {"user_id": str(user_id), "usage_date": today, "turn_count": new_turn_count}
    ).execute()

    remaining = settings.ai_tutor_daily_turn_limit - new_turn_count
    line_client.reply_flex(
        reply_token,
        alt_text="AI 助教回覆",
        contents=flex_templates.build_ai_tutor_reply_card(answer, mode, f"（今日還可以追問 {remaining} 次）"),
    )
