import re
import threading
from typing import Optional
from uuid import UUID

from app.config import settings
from app.db.client import supabase
from app.services.ai_client import chat_completion
from app.services.question_picker import option_text

FEEDBACK_SYSTEM_PROMPT = """你是一套日語教學系統的解釋型回饋生成器，任務是向學習者說明他剛剛作答的這一題「為什麼這個答案正確／錯誤」以及「正確用法的判斷依據」。

嚴格限制（必須遵守）：
- 你只能依據使用者訊息中提供的「解釋依據」來說明，不可以引入解釋依據沒有提到的額外文法規則、單字知識或其他背景知識。
- 若解釋依據內容不足以完整說明，也不要自行補充，只根據給定內容盡量說明即可。
- 使用繁體中文回覆，語氣像老師講解，簡潔清楚，2 到 4 句話即可，不要加上多餘的招呼語。
- 解釋依據裡可能包含日文原文（例如日文寫的意思說明、例句）。你可以引用日語詞彙本身（例如諺語、單字）與它的讀音／假名，但說明的句子本身必須完全用你自己的話翻譯、改寫成繁體中文——絕對不可以把解釋依據裡的日文說明句子原封不動貼進回覆裡。"""


def extract_example_sentence(explanation_rule: Optional[str]) -> Optional[str]:
    """從解析原文裡取出【例文】欄位內容，原封不動顯示在回饋卡片上（不經 AI 改寫），
    因為 AI 生成回饋時經常會把例句省略掉。非諺語模式或解析裡沒有這個欄位時回傳 None。
    """
    if not explanation_rule:
        return None
    match = re.search(r"【例文】(.*?)(?:【|$)", explanation_rule, re.DOTALL)
    return match.group(1).strip() if match else None


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


def generate_feedback_text(
    context_sentence: str,
    correct_option_text: str,
    selected_option_text: str,
    explanation_rule: str,
    is_correct: bool,
) -> str:
    """只呼叫 AI 生成回饋文字，不寫入 feedback_logs。這段不需要 attempt_log_id，
    所以呼叫端可以把這個呼叫跟寫 attempts_log 的 DB 操作平行執行（AI 生成通常比整段
    DB 寫入還慢，平行跑可以讓使用者少等一段時間），確定要用的時候再呼叫 log_feedback。
    """
    messages = _build_messages(
        context_sentence, correct_option_text, selected_option_text, explanation_rule, is_correct
    )
    return chat_completion(messages)


def log_feedback(attempt_log_id: UUID, ai_generated_text: str) -> None:
    supabase.table("feedback_logs").insert(
        {
            "attempt_log_id": str(attempt_log_id),
            "ai_generated_text": ai_generated_text,
            "model_used": settings.openai_model,
            "human_reviewed": False,
        }
    ).execute()


def generate_and_log_feedback(
    attempt_log_id: UUID,
    context_sentence: str,
    correct_option_text: str,
    selected_option_text: str,
    explanation_rule: str,
    is_correct: bool,
) -> str:
    text = generate_feedback_text(
        context_sentence, correct_option_text, selected_option_text, explanation_rule, is_correct
    )
    log_feedback(attempt_log_id, text)
    return text


def start_feedback_generation(question: dict, opt: Optional[str], is_correct: bool):
    """単語模式沒有 AI 生成（見 finish_feedback_text），回傳 (None, {})。其他模式在背景
    執行緒起跑 AI 呼叫，跟隨後的 finalize_attempt（DB 寫入）平行執行——AI 生成通常比整段
    DB 寫入還慢，且不需要 attempt id，提前起跑可以減少使用者實際等待的總時間。單語／
    諺／言語知識三模式的一般練習、複習、每日挑戰共用這組邏輯。回傳 (thread, result_dict)。
    """
    if question["mode"] == "vocab":
        return None, {}

    result: dict = {}

    def _run() -> None:
        result["text"] = generate_feedback_text(
            context_sentence=question.get("context_sentence") or "",
            correct_option_text=option_text(question, question.get("correct_option")),
            selected_option_text=option_text(question, opt),
            explanation_rule=question.get("explanation_rule") or "",
            is_correct=is_correct,
        )

    thread = threading.Thread(target=_run)
    thread.start()
    return thread, result


def finish_feedback_text(
    question: dict, attempt_id: UUID, feedback_thread, feedback_result: dict
) -> tuple[str, Optional[str]]:
    """回傳 (回饋文字, 例句原文)。単語模式只考讀音，答案本身沒有需要說明的細膩語感，
    所以不呼叫 AI、不寫 feedback_logs，直接告知正確讀音；諺／言語知識維持原本的 AI
    生成流程（依 explanation_rule 為解釋依據）。"""
    if question["mode"] == "vocab":
        correct_reading = option_text(question, question.get("correct_option"))
        return f"正確讀音是「{correct_reading}」。", None

    feedback_thread.join()
    feedback_text = feedback_result["text"]
    log_feedback(attempt_id, feedback_text)
    example_sentence = extract_example_sentence(question.get("explanation_rule"))
    return feedback_text, example_sentence
