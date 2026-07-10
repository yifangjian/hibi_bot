"""共用的 rich menu alias 命名邏輯，供 scripts/setup_richmenu.py 與需要組出 richMenuAliasId
的地方（例如 AI 助教回覆卡片的「結束討論」按鈕）共用，避免兩邊各自定義造成命名不一致。"""

ALIAS_MAIN = "alias_main"

# LINE 的 richMenuAliasId 上限 32 字元，"language_knowledge" 太長，故 alias 用短碼；
# postback data 裡的 mode 參數仍維持完整字串，不受此限制影響
ALIAS_MODE_CODE = {"vocab": "vocab", "proverb": "proverb", "language_knowledge": "lk"}


def mode_alias(prefix: str, mode: str) -> str:
    return f"alias_{prefix}_{ALIAS_MODE_CODE[mode]}"
