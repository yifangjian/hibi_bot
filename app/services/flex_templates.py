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
