from typing import Any, Optional

BACKGROUND = "#FAF3E3"
SEPARATOR = "#E4DCC8"
NAVY = "#1C2B44"
CORAL = "#B23A3A"
MUTED = "#8A8578"

MODE_LABELS = {"vocab": "単語", "proverb": "諺", "language_knowledge": "言語知識"}


def _context_sentence_contents(context_sentence: str, blank_marker: Optional[str]) -> list:
    if blank_marker and blank_marker in context_sentence:
        before, after = context_sentence.split(blank_marker, 1)
        contents = []
        if before:
            contents.append({"type": "span", "text": before})
        contents.append(
            {"type": "span", "text": blank_marker, "color": CORAL, "weight": "bold", "decoration": "underline"}
        )
        if after:
            contents.append({"type": "span", "text": after})
        return contents
    return [{"type": "span", "text": context_sentence}]


def _option_box(option: dict[str, Any], data: str) -> dict:
    """可完整顯示長選項文字的可點擊選項列。LINE 的 button 元件文字取自 action.label，
    這個欄位官方硬性限制最多 20 字元，長選項（例如完整句子）會被截斷。改用 box 掛
    action，視覺文字改放在裡面的 text 元件（wrap=True），不受這個限制；label 只放
    簡短的「選項X」供無障礙輔助使用，不影響實際顯示內容。
    """
    short_label = f"選項{option['id'].upper()}"
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": NAVY,
        "cornerRadius": "md",
        "paddingAll": "12px",
        "action": {
            "type": "postback",
            "label": short_label,
            "data": data,
            "displayText": option["text"],
        },
        "contents": [
            {
                "type": "text",
                "text": option["text"],
                "wrap": True,
                "size": "sm",
                "color": "#FFFFFF",
                "align": "center",
            }
        ],
    }


def build_question_card(question: dict[str, Any], action: str = "answer") -> dict:
    """単語 / 諺第一階段 / 言語知識共用的出題卡片。action 預設為一般練習的 "answer"，
    複習錯題模式會傳入 "review_answer" 讓後端區分這是複習還是初次作答。"""
    stage = question.get("stage")
    stage_param = f"&stage={stage}" if stage else "&stage=1"

    option_buttons = [
        _option_box(option, f"action={action}&qid={question['id']}&opt={option['id']}{stage_param}")
        for option in question.get("options") or []
    ]

    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": BACKGROUND,
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": f"範圍：{question['exam_scope']}", "size": "xs", "color": MUTED},
                {"type": "separator", "margin": "md", "color": SEPARATOR},
                {
                    "type": "text",
                    "wrap": True,
                    "margin": "lg",
                    "size": "md",
                    "weight": "bold",
                    "color": NAVY,
                    "contents": _context_sentence_contents(
                        question.get("context_sentence") or "", question.get("blank_marker")
                    ),
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xl",
                    "spacing": "md",
                    "contents": option_buttons,
                },
            ],
        },
    }


def build_reading_input_prompt_card(question: dict[str, Any]) -> dict:
    """諺第二階段：讀音輸入提示卡片，不放按鈕。"""
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": BACKGROUND,
            "paddingAll": "20px",
            "contents": [
                {
                    "type": "text",
                    "text": "請輸入這個諺語的讀音",
                    "weight": "bold",
                    "size": "md",
                    "color": NAVY,
                },
                {
                    "type": "text",
                    "text": "（請直接在聊天室輸入平假名回覆）",
                    "size": "sm",
                    "color": MUTED,
                    "wrap": True,
                    "margin": "md",
                },
            ],
        },
    }


def build_daily_challenge_start_card(challenge_id: str) -> dict:
    """每日挑戰推播卡片：提示文字 + 開始/繼續挑戰按鈕。"""
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": BACKGROUND,
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": "🎉 每日挑戰來了！", "weight": "bold", "size": "lg", "color": NAVY},
                {
                    "type": "text",
                    "text": "完成 5 題挑戰，看看今天的表現吧！",
                    "wrap": True,
                    "size": "sm",
                    "color": MUTED,
                    "margin": "md",
                },
                {
                    "type": "button",
                    "style": "primary",
                    "color": NAVY,
                    "margin": "xl",
                    "action": {
                        "type": "postback",
                        "label": "開始挑戰",
                        "data": f"action=daily_challenge_start&challenge_id={challenge_id}",
                        "displayText": "開始挑戰",
                    },
                },
            ],
        },
    }


def build_challenge_question_card(question: dict[str, Any], challenge_id: str, progress_text: str) -> dict:
    """每日挑戰的出題卡片：結構與 build_question_card 相同，但按鈕 postback 帶入
    challenge_id（供辨識過期挑戰），上方顯示挑戰進度而非單元。"""
    stage = question.get("stage")
    stage_param = f"&stage={stage}" if stage else "&stage=1"

    option_buttons = [
        _option_box(
            option,
            (
                f"action=daily_challenge_answer&challenge_id={challenge_id}"
                f"&qid={question['id']}&opt={option['id']}{stage_param}"
            ),
        )
        for option in question.get("options") or []
    ]

    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": BACKGROUND,
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": progress_text, "size": "xs", "color": MUTED},
                {"type": "separator", "margin": "md", "color": SEPARATOR},
                {
                    "type": "text",
                    "wrap": True,
                    "margin": "lg",
                    "size": "md",
                    "weight": "bold",
                    "color": NAVY,
                    "contents": _context_sentence_contents(
                        question.get("context_sentence") or "", question.get("blank_marker")
                    ),
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "xl",
                    "spacing": "md",
                    "contents": option_buttons,
                },
            ],
        },
    }


def build_ai_tutor_reply_card(answer_text: str, mode: str, remaining_text: Optional[str] = None) -> dict:
    """AI 助教回覆卡片（初次解析／追問共用）：內容 + 剩餘額度提示（若有）+「問其他題」／「繼續練習」按鈕。"""
    contents: list[dict] = [
        {"type": "text", "text": answer_text, "wrap": True, "size": "sm", "color": NAVY},
    ]
    if remaining_text:
        contents.append(
            {"type": "text", "text": remaining_text, "wrap": True, "size": "xs", "color": MUTED, "margin": "md"}
        )

    contents.append(
        {
            "type": "box",
            "layout": "horizontal",
            "margin": "xl",
            "spacing": "md",
            "contents": [
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "postback",
                        "label": "問其他題",
                        "data": f"action=ai_tutor_prompt&mode={mode}",
                        "displayText": "問其他題",
                    },
                },
                {
                    "type": "button",
                    "style": "primary",
                    "color": NAVY,
                    "action": {
                        "type": "postback",
                        "label": "繼續練習",
                        "data": f"action=next_question&mode={mode}",
                        "displayText": "繼續練習",
                    },
                },
            ],
        }
    )

    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": BACKGROUND,
            "paddingAll": "20px",
            "contents": contents,
        },
    }


def build_feedback_card(
    is_correct: bool, explanation_text: str, mode: str, retry_action: str = "next_question"
) -> dict:
    """三模式共用的回饋卡片。retry_action 預設 "next_question"（一般練習的「再練一題」），
    複習錯題模式會傳入 "review_wrong"，按鈕文字與行為會跟著切換成「繼續複習」。"""
    retry_label = "繼續複習" if retry_action == "review_wrong" else "再練一題"

    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": BACKGROUND,
            "paddingAll": "20px",
            "contents": [
                {
                    "type": "text",
                    "text": "✓ 答對了" if is_correct else "✗ 答錯了",
                    "weight": "bold",
                    "size": "xl",
                    "color": NAVY if is_correct else CORAL,
                },
                {"type": "separator", "margin": "md", "color": SEPARATOR},
                {
                    "type": "text",
                    "text": explanation_text or "（尚無解釋內容）",
                    "wrap": True,
                    "margin": "lg",
                    "size": "sm",
                    "color": NAVY,
                },
                {
                    "type": "button",
                    "style": "primary",
                    "color": NAVY,
                    "margin": "xl",
                    "action": {
                        "type": "postback",
                        "label": retry_label,
                        "data": f"action={retry_action}&mode={mode}",
                        "displayText": retry_label,
                    },
                },
            ],
        },
    }


def _mode_progress_section(summary: dict[str, Any]) -> dict:
    label = MODE_LABELS.get(summary["mode"], summary["mode"])

    if summary.get("no_data"):
        return {
            "type": "box",
            "layout": "vertical",
            "margin": "lg",
            "contents": [
                {"type": "text", "text": label, "weight": "bold", "size": "md", "color": NAVY},
                {"type": "text", "text": "尚未開始練習", "size": "sm", "color": MUTED, "margin": "sm"},
            ],
        }

    return {
        "type": "box",
        "layout": "vertical",
        "margin": "lg",
        "contents": [
            {
                "type": "text",
                "text": f"{label}　範圍：{summary['exam_scope']}・第 {summary['current_round']} 輪",
                "weight": "bold",
                "size": "md",
                "color": NAVY,
                "wrap": True,
            },
            {
                "type": "text",
                "text": f"本輪進度：{summary['attempted_count']}/{summary['total']} 題",
                "size": "sm",
                "color": MUTED,
                "margin": "sm",
            },
            {
                "type": "text",
                "text": f"待複習錯題：{summary['wrong_count']} 題",
                "size": "sm",
                "color": CORAL if summary["wrong_count"] > 0 else MUTED,
                "margin": "xs",
            },
        ],
    }


def build_progress_card(mode_summaries: list[dict[str, Any]], completed_challenge_count: int) -> dict:
    """我的進度卡片：三模式各自的單元/輪次/本輪進度/待複習錯題數，
    加上每日挑戰累計完成次數（刻意不做連續天數，避免中斷造成挫折感）。"""
    contents: list[dict] = [
        {"type": "text", "text": "📊 我的進度", "weight": "bold", "size": "lg", "color": NAVY},
        {"type": "separator", "margin": "md", "color": SEPARATOR},
    ]

    for summary in mode_summaries:
        contents.append(_mode_progress_section(summary))

    contents.append({"type": "separator", "margin": "lg", "color": SEPARATOR})
    contents.append(
        {
            "type": "text",
            "text": f"🎉 每日挑戰累計完成：{completed_challenge_count} 次",
            "size": "sm",
            "color": NAVY,
            "margin": "lg",
            "wrap": True,
        }
    )

    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": BACKGROUND,
            "paddingAll": "20px",
            "contents": contents,
        },
    }
