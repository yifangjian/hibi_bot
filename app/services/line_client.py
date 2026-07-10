from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    FlexMessage,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.messaging.models.flex_container import FlexContainer

from app.config import settings


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
