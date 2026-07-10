"""
建立並上傳 hibi_bot 的圖文選單（Rich Menu）到 LINE。

手動執行一次即可，不放進 webhook 常駐流程：

    python scripts/setup_richmenu.py

執行後會在專案根目錄產生 richmenu_ids.json，記錄所有 richMenuId 與 aliasId。
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from linebot.v3.messaging import (  # noqa: E402
    ApiClient,
    Configuration,
    CreateRichMenuAliasRequest,
    MessagingApi,
    MessagingApiBlob,
    PostbackAction,
    RichMenuArea,
    RichMenuBounds,
    RichMenuRequest,
    RichMenuSize,
    RichMenuSwitchAction,
)

from app.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("setup_richmenu")

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "richmenu"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "richmenu_ids.json"

MODES = ["vocab", "proverb", "language_knowledge"]

ALIAS_MAIN = "alias_main"

# LINE 的 richMenuAliasId 上限 32 字元，"language_knowledge" 太長，故 alias 用短碼；
# postback data 裡的 mode 參數仍維持完整字串，不受此限制影響
ALIAS_MODE_CODE = {"vocab": "vocab", "proverb": "proverb", "language_knowledge": "lk"}


def mode_alias(prefix: str, mode: str) -> str:
    return f"alias_{prefix}_{ALIAS_MODE_CODE[mode]}"


def area(x: int, y: int, width: int, height: int, action) -> RichMenuArea:
    return RichMenuArea(bounds=RichMenuBounds(x=x, y=y, width=width, height=height), action=action)


def switch_action(label: str, alias_id: str, data: str) -> RichMenuSwitchAction:
    return RichMenuSwitchAction(label=label, rich_menu_alias_id=alias_id, data=data)


def postback_action(label: str, data: str) -> PostbackAction:
    return PostbackAction(label=label, data=data, display_text=label)


def build_main_menu_areas() -> list:
    return [
        area(0, 0, 1250, 843, switch_action("単語", mode_alias("mode", "vocab"), "action=enter_mode&mode=vocab")),
        area(1250, 0, 1250, 843, switch_action("諺", mode_alias("mode", "proverb"), "action=enter_mode&mode=proverb")),
        area(
            0,
            843,
            1250,
            843,
            switch_action(
                "言語知識",
                mode_alias("mode", "language_knowledge"),
                "action=enter_mode&mode=language_knowledge",
            ),
        ),
        area(1250, 843, 1250, 843, postback_action("我的進度", "action=view_progress&scope=all")),
    ]


def build_mode_menu_areas(mode: str) -> list:
    return [
        area(
            0,
            0,
            833,
            843,
            switch_action("開始練習", mode_alias("start_practice", mode), f"action=start_practice&mode={mode}"),
        ),
        area(
            833,
            0,
            833,
            843,
            switch_action(
                "錯題模式", mode_alias("wrong_question", mode), f"action=enter_wrong_mode&mode={mode}"
            ),
        ),
        area(1666, 0, 834, 843, postback_action("進度", f"action=view_progress&mode={mode}")),
        area(0, 843, 833, 843, postback_action("重置", f"action=reset_unit&mode={mode}")),
        area(833, 843, 1667, 843, switch_action("返回", ALIAS_MAIN, "action=back&to=main_menu")),
    ]


def build_start_practice_menu_areas(mode: str) -> list:
    return [
        area(0, 0, 1250, 843, postback_action("AI助教", f"action=ai_tutor_prompt&mode={mode}")),
        area(
            1250,
            0,
            1250,
            843,
            switch_action("返回", mode_alias("mode", mode), f"action=back&to=mode_menu&mode={mode}"),
        ),
    ]


def build_wrong_question_menu_areas(mode: str) -> list:
    return [
        area(0, 0, 1250, 843, postback_action("複習錯題", f"action=review_wrong&mode={mode}")),
        area(
            1250,
            0,
            1250,
            843,
            switch_action("返回", mode_alias("mode", mode), f"action=back&to=mode_menu&mode={mode}"),
        ),
    ]


def create_and_upload(
    api: MessagingApi,
    blob_api: MessagingApiBlob,
    name: str,
    chat_bar_text: str,
    width: int,
    height: int,
    areas: list,
    image_path: Path,
    selected: bool = False,
) -> str:
    request = RichMenuRequest(
        size=RichMenuSize(width=width, height=height),
        selected=selected,
        name=name,
        chat_bar_text=chat_bar_text,
        areas=areas,
    )
    response = api.create_rich_menu(rich_menu_request=request)
    rich_menu_id = response.rich_menu_id
    logger.info("建立 rich menu「%s」-> %s", name, rich_menu_id)

    image_bytes = image_path.read_bytes()
    blob_api.set_rich_menu_image(rich_menu_id, body=image_bytes, _headers={"Content-Type": "image/png"})
    logger.info("已上傳圖片：%s", image_path.name)

    return rich_menu_id


def create_alias(api: MessagingApi, alias_id: str, rich_menu_id: str) -> None:
    api.create_rich_menu_alias(
        create_rich_menu_alias_request=CreateRichMenuAliasRequest(
            rich_menu_alias_id=alias_id, rich_menu_id=rich_menu_id
        )
    )
    logger.info("建立 alias「%s」-> %s", alias_id, rich_menu_id)


def main() -> None:
    configuration = Configuration(access_token=settings.line_channel_access_token)
    result: dict = {}

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        blob_api = MessagingApiBlob(api_client)

        # 1. 建立每張圖對應的 rich menu 並上傳圖片內容
        main_menu_id = create_and_upload(
            api,
            blob_api,
            name="main_menu",
            chat_bar_text="選單",
            width=2500,
            height=1686,
            areas=build_main_menu_areas(),
            image_path=ASSETS_DIR / "main_menu.png",
            selected=True,
        )
        result["main_menu"] = {"rich_menu_id": main_menu_id, "alias_id": ALIAS_MAIN}

        result["mode_menu"] = {}
        for mode in MODES:
            rich_menu_id = create_and_upload(
                api,
                blob_api,
                name=f"mode_menu_{mode}",
                chat_bar_text="模式選單",
                width=2500,
                height=1686,
                areas=build_mode_menu_areas(mode),
                image_path=ASSETS_DIR / "mode_menu.png",
            )
            result["mode_menu"][mode] = {
                "rich_menu_id": rich_menu_id,
                "alias_id": mode_alias("mode", mode),
            }

        result["start_practice_menu"] = {}
        for mode in MODES:
            rich_menu_id = create_and_upload(
                api,
                blob_api,
                name=f"start_practice_menu_{mode}",
                chat_bar_text="開始練習",
                width=2500,
                height=843,
                areas=build_start_practice_menu_areas(mode),
                image_path=ASSETS_DIR / "start_practice_menu.png",
            )
            result["start_practice_menu"][mode] = {
                "rich_menu_id": rich_menu_id,
                "alias_id": mode_alias("start_practice", mode),
            }

        result["wrong_question_menu"] = {}
        for mode in MODES:
            rich_menu_id = create_and_upload(
                api,
                blob_api,
                name=f"wrong_question_menu_{mode}",
                chat_bar_text="錯題複習",
                width=2500,
                height=843,
                areas=build_wrong_question_menu_areas(mode),
                image_path=ASSETS_DIR / "wrong_question_menu.png",
            )
            result["wrong_question_menu"][mode] = {
                "rich_menu_id": rich_menu_id,
                "alias_id": mode_alias("wrong_question", mode),
            }

        # 2. 建立所有 alias（richmenuswitch action 用字串 alias id 在點擊當下才解析，
        #    所以不需要照特定順序建立）
        create_alias(api, ALIAS_MAIN, main_menu_id)
        for mode in MODES:
            create_alias(api, mode_alias("mode", mode), result["mode_menu"][mode]["rich_menu_id"])
            create_alias(
                api, mode_alias("start_practice", mode), result["start_practice_menu"][mode]["rich_menu_id"]
            )
            create_alias(
                api, mode_alias("wrong_question", mode), result["wrong_question_menu"][mode]["rich_menu_id"]
            )

        # 3. 將 main_menu 設為所有使用者的預設選單
        api.set_default_rich_menu(rich_menu_id=main_menu_id)
        logger.info("已將「main_menu」設為預設選單")

    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("已寫入 %s", OUTPUT_PATH)


if __name__ == "__main__":
    main()
