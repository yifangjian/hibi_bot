from uuid import UUID

from app.config import settings
from app.db.client import supabase
from app.services.ai_client import chat_completion

FEEDBACK_SYSTEM_PROMPT = """你是一套日語教學系統的解釋型回饋生成器，任務是向學習者說明他剛剛作答的這一題「為什麼這個答案正確／錯誤」以及「正確用法的判斷依據」。

嚴格限制（必須遵守）：
- 你只能依據使用者訊息中提供的「解釋依據」來說明，不可以引入解釋依據沒有提到的額外文法規則、單字知識或其他背景知識。
- 若解釋依據內容不足以完整說明，也不要自行補充，只根據給定內容盡量說明即可。
- 使用繁體中文回覆，語氣像老師講解，簡潔清楚，2 到 4 句話即可，不要加上多餘的招呼語。"""


def _build_messages(
    context_sentence: str,
    correct_option_text: str,
    selected_option_text: str,
    explanation_rule: str,
    is_correct: bool,
) -> list[dict]:
    user_content = (
        f"題目情境：{context_sentence}\n"
        f"使用者的答案：{selected_option_text}\n"
        f"正確答案：{correct_option_text}\n"
        f"作答結果：{'正確' if is_correct else '錯誤'}\n"
        f"解釋依據：{explanation_rule}"
    )
    return [
        {"role": "system", "content": FEEDBACK_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def generate_and_log_feedback(
    attempt_log_id: UUID,
    context_sentence: str,
    correct_option_text: str,
    selected_option_text: str,
    explanation_rule: str,
    is_correct: bool,
) -> str:
    messages = _build_messages(
        context_sentence, correct_option_text, selected_option_text, explanation_rule, is_correct
    )
    text = chat_completion(messages)

    supabase.table("feedback_logs").insert(
        {
            "attempt_log_id": str(attempt_log_id),
            "ai_generated_text": text,
            "model_used": settings.openai_model,
            "human_reviewed": False,
        }
    ).execute()

    return text
