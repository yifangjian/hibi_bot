from typing import Any, Optional

BACKGROUND = "#FAF3E3"
SEPARATOR = "#E4DCC8"
NAVY = "#1C2B44"
CORAL = "#B23A3A"
MUTED = "#8A8578"


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


def build_question_card(question: dict[str, Any]) -> dict:
    """単語 / 諺第一階段 / 言語知識共用的出題卡片。"""
    stage = question.get("stage")
    stage_param = f"&stage={stage}" if stage else "&stage=1"

    option_buttons = [
        {
            "type": "button",
            "style": "primary",
            "color": NAVY,
            "action": {
                "type": "postback",
                "label": option["text"],
                "data": f"action=answer&qid={question['id']}&opt={option['id']}{stage_param}",
                "displayText": option["text"],
            },
        }
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
                {"type": "text", "text": f"第 {question['unit_number']} 單元", "size": "xs", "color": MUTED},
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
        {
            "type": "button",
            "style": "primary",
            "color": NAVY,
            "action": {
                "type": "postback",
                "label": option["text"],
                "data": (
                    f"action=daily_challenge_answer&challenge_id={challenge_id}"
                    f"&qid={question['id']}&opt={option['id']}{stage_param}"
                ),
                "displayText": option["text"],
            },
        }
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


def build_feedback_card(is_correct: bool, explanation_text: str, mode: str) -> dict:
    """三模式共用的回饋卡片。"""
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
                        "label": "再練一題",
                        "data": f"action=next_question&mode={mode}",
                        "displayText": "再練一題",
                    },
                },
            ],
        },
    }
