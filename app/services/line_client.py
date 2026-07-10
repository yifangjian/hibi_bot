from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    FlexMessage,
    ImageMessage,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.messaging.models.flex_container import FlexContainer

from app.config import settings
from app.services.rich_menu_alias import ALIAS_MAIN


def _client() -> MessagingApi:
    configuration = Configuration(access_token=settings.line_channel_access_token)
    return MessagingApi(ApiClient(configuration))


def reply_flex(reply_token: str, alt_text: str, contents: dict) -> None:
    _client().reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[FlexMessage(alt_text=alt_text, contents=FlexContainer.from_dict(contents))],
        )
    )


def reply_text(reply_token: str, text: str) -> None:
    _client().reply_message(
        ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)])
    )


def reply_image(reply_token: str, image_url: str) -> None:
    _client().reply_message(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[ImageMessage(original_content_url=image_url, preview_image_url=image_url)],
        )
    )


def push_flex(line_user_id: str, alt_text: str, contents: dict) -> None:
    _client().push_message(
        PushMessageRequest(
            to=line_user_id,
            messages=[FlexMessage(alt_text=alt_text, contents=FlexContainer.from_dict(contents))],
        )
    )


def get_display_name(line_user_id: str) -> str:
    profile = _client().get_profile(user_id=line_user_id)
    return profile.display_name


def switch_rich_menu_to_main(line_user_id: str) -> None:
    api = _client()
    alias = api.get_rich_menu_alias(rich_menu_alias_id=ALIAS_MAIN)
    api.link_rich_menu_id_to_user(user_id=line_user_id, rich_menu_id=alias.rich_menu_id)
