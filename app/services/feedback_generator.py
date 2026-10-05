import re
import threading
import unicodedata
from typing import Optional
from uuid import UUID

from app.config import settings
from app.db.client import supabase
from app.services.ai_client import chat_completion_json
from app.services.question_picker import option_text

FEEDBACK_SYSTEM_PROMPT = """你是日語老師，要為學生剛作答的一題寫解說，依 JSON 欄位分別填寫：

- correct：正確答案的說明。先寫出正確選項（詞語寫成「漢字（讀音）」），再用中文說明它的意思，並指出題目句子裡哪些字詞是判斷的線索、為什麼放進這個句子是通順的。如果題目沒有情境句，只是問某個諺語或詞語「的意思是哪一個」，就不要找題目句的線索，改成說明它的意思，再借用解析裡例句的情境，說明它平常在什麼場合使用。
- chosen：學生答錯時，先說明學生選的選項是什麼、什麼意思，再用一句話點出它和正確答案的關鍵差別（兩者各用在什麼情況、語意或搭配差在哪），讓學生知道為什麼放進這個句子不通。學生答對時填空字串。
- others：只針對使用者訊息中「其他選項」列出的每一個各寫一項，label 填選項代號（A/B/C/D）；explanation 用一句話說明它的意思：詞語選項寫成「詞語（讀音）＝中文意思」，選項本身是日文句子時只寫中文轉述。

規則（必須遵守）：
- 只使用使用者訊息中提供的資訊（題目、選項、解析與各選項說明），不要自行捏造或補充沒提到的文法規則、詞義。
- 選項顯示的可能是讀音（平假名），解析裡則用漢字寫，請自行對應（例如選項「きょうだん」對應解析的「教壇」）。
- 不要寫出「解釋依據」「依據」「資料」「解析中」「提供的說明」這類字眼，直接用老師講課的口吻說明。
- 不要用「例句就是這樣寫」來證明答案正確——情境題的例句就是題目句本身，那是循環論證。
- 使用繁體中文。日文只能出現在兩種地方：詞語或諺語本身（附讀音），以及從題目句引用的簡短線索字詞；解析裡的日文說明句、日文選項句一律用中文轉述，絕不可原句照貼。
- 不要招呼語、不要結語；correct 約 60 字以內，chosen 約 80 字以內（要容納和正解的比較），others 每項一句。"""

FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "correct": {"type": "string"},
        "chosen": {"type": "string"},
        "others": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"label": {"type": "string"}, "explanation": {"type": "string"}},
                "required": ["label", "explanation"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["correct", "chosen", "others"],
    "additionalProperties": False,
}


SEMANTIC_CHOICE_HINT = (
    "這是「選出諺語意思」的題目：題目沒有情境句，選項都是日文的意思說明句。"
    "所有欄位提到任何選項時，一律只寫中文轉述，完全不要出現選項或解析裡的日文說明句。"
)


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
    all_options_text: str = "",
    other_options: Optional[list[str]] = None,
    hint: str = "",
) -> list[dict]:
    user_content = (
        (f"題型提醒：{hint}\n" if hint else "")
        + f"題目：{context_sentence}\n"
        + (f"選項：{all_options_text}\n" if all_options_text else "")
        + f"正確答案：{correct_option_text}\n"
        f"學生選的：{selected_option_text}\n"
        + (f"其他選項：{'　'.join(other_options)}\n" if other_options else "其他選項：（無）\n")
        + f"作答結果：{'答對' if is_correct else '答錯'}\n"
        f"解析：{explanation_rule}"
    )
    return [
        {"role": "system", "content": FEEDBACK_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _drop_japanese_prefix(text: str) -> str:
    """模型偶爾會寫成「日文選項原句＝中文意思」。等號左邊若是一長串（超過 12 字，代表是
    整句日文說明而不是單一詞語），只留右邊的中文。詞語選項（例如「花束（はなたば）＝…」）
    左邊很短，維持原樣。"""
    if "＝" in text:
        left, right = text.split("＝", 1)
        if len(left) > 12 and right.strip():
            return right.strip()
    return text


_ALLOWED_SCRIPTS = ("CJK", "HIRAGANA", "KATAKANA", "LATIN", "FULLWIDTH", "HALFWIDTH", "IDEOGRAPHIC")


def _has_foreign_script(result: dict) -> bool:
    """回傳內容是否混入中日文與拉丁字母以外的文字（天城文、西里爾字母等）。"""
    texts = [result["correct"], result["chosen"]] + [item["explanation"] for item in result["others"]]
    return any(
        unicodedata.category(ch).startswith("L") and not unicodedata.name(ch, "").startswith(_ALLOWED_SCRIPTS)
        for text in texts
        for ch in text
    )


def generate_feedback_text(
    context_sentence: str,
    correct_option_text: str,
    selected_option_text: str,
    explanation_rule: str,
    is_correct: bool,
    all_options_text: str = "",
    other_options: Optional[list[str]] = None,
    hint: str = "",
) -> str:
    """只呼叫 AI 生成回饋文字，不寫入 feedback_logs。這段不需要 attempt_log_id，
    所以呼叫端可以把這個呼叫跟寫 attempts_log 的 DB 操作平行執行（AI 生成通常比整段
    DB 寫入還慢，平行跑可以讓使用者少等一段時間），確定要用的時候再呼叫 log_feedback。

    AI 只負責分欄位填內容，段落由這裡組裝：「你選的」只在答錯時出現、「其他選項」依
    other_options 的順序且不含正解與學生選的——這兩點只靠提示詞要求，實測模型常常不照做。
    other_options 每項格式為「C. 選項文字」，以開頭的代號對應 AI 回傳的 label。
    """
    messages = _build_messages(
        context_sentence,
        correct_option_text,
        selected_option_text,
        explanation_rule,
        is_correct,
        all_options_text,
        other_options,
        hint,
    )
    result = chat_completion_json(messages, "answer_feedback", FEEDBACK_SCHEMA)
    if _has_foreign_script(result):
        # 模型偶爾會冒出其他語系的字（實測出現過「協議後 तय好的約定」），重生一次
        result = chat_completion_json(messages, "answer_feedback", FEEDBACK_SCHEMA)

    parts = [f"正解：{result['correct'].strip()}"]
    chosen = re.sub(r"^你選的[：:]?\s*", "", result["chosen"].strip())  # 段落標題由程式加，模型偶爾自己也寫一次
    if not is_correct and chosen:
        parts.append(f"你選的：{chosen}")
    by_label = {
        item["label"].strip().upper()[:1]: _drop_japanese_prefix(item["explanation"].strip()) for item in result["others"]
    }
    wanted = [o.split(".", 1)[0].strip().upper() for o in (other_options or [])]
    others = [by_label[label] for label in wanted if by_label.get(label)]
    if others:
        parts.append("其他選項：" + "／".join(others))
    return "\n\n".join(parts)


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


def has_no_explanation(question: dict) -> bool:
    """前測（暑修班）的単語題庫是純讀音測驗、沒有解析，答題後只顯示正確讀音、不呼叫 AI。
    115 學年起的単語題庫改成情境句挖空且每題附解析，就跟諺／言語知識一樣走 AI 生成。
    用「有沒有 explanation_rule」判斷，而不是看 mode，舊範圍的題目行為才不會跟著改變。"""
    return question["mode"] == "vocab" and not (question.get("explanation_rule") or "").strip()


def _labeled_option(question: dict, option_id: Optional[str]) -> str:
    """把選項代號跟文字一起給 AI（例如「A. きょうだん」），解析裡的【他の選択肢】是用
    A/B/C/D 標示，AI 才能把學生選的讀音對應到解析寫的漢字與意思。多重正確答案（「a、c」）
    會列出每一個。"""
    ids = [i for i in (option_id or "").split("、") if i]
    return "、".join(f"{i.upper()}. {option_text(question, i)}" for i in ids)


def start_feedback_generation(question: dict, opt: Optional[str], is_correct: bool):
    """沒有解析的舊単語題不呼叫 AI（見 finish_feedback_text），回傳 (None, {})。其他題目在背景
    執行緒起跑 AI 呼叫，跟隨後的 finalize_attempt（DB 寫入）平行執行——AI 生成通常比整段
    DB 寫入還慢，且不需要 attempt id，提前起跑可以減少使用者實際等待的總時間。單語／
    諺／言語知識三模式的一般練習、複習、每日挑戰共用這組邏輯。回傳 (thread, result_dict)。
    """
    if has_no_explanation(question):
        return None, {}

    result: dict = {}
    excluded = set((question.get("correct_option") or "").split("、")) | {opt}

    def _run() -> None:
        result["text"] = generate_feedback_text(
            context_sentence=question.get("context_sentence") or "",
            correct_option_text=_labeled_option(question, question.get("correct_option")),
            selected_option_text=_labeled_option(question, opt),
            explanation_rule=question.get("explanation_rule") or "",
            is_correct=is_correct,
            all_options_text="　".join(
                f"{o['id'].upper()}. {o['text']}" for o in (question.get("options") or [])
            ),
            other_options=[
                f"{o['id'].upper()}. {o['text']}"
                for o in (question.get("options") or [])
                if o["id"] not in excluded
            ],
            hint=SEMANTIC_CHOICE_HINT if question.get("stage") == "semantic_choice" else "",
        )

    thread = threading.Thread(target=_run)
    thread.start()
    return thread, result


def finish_feedback_text(
    question: dict, attempt_id: UUID, feedback_thread, feedback_result: dict
) -> tuple[str, Optional[str]]:
    """回傳 (回饋文字, 例句原文)。沒有解析的舊単語題（純讀音測驗）不呼叫 AI、不寫
    feedback_logs，直接告知正確讀音；其他題目走 AI 生成流程（依 explanation_rule 為解釋依據）。"""
    if has_no_explanation(question):
        correct_ids = (question.get("correct_option") or "").split("、")
        readings = "、".join(option_text(question, cid) for cid in correct_ids)
        return f"正確讀音是「{readings}」。", None

    feedback_thread.join()
    feedback_text = feedback_result["text"]
    log_feedback(attempt_id, feedback_text)
    example_sentence = extract_example_sentence(question.get("explanation_rule"))
    return feedback_text, example_sentence
