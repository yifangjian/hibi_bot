import logging
from typing import Optional
from uuid import UUID

logger = logging.getLogger("hibi_bot.menu_actions")


def handle_enter_mode(user_id: UUID, params: dict) -> None:
    logger.info("Stub handle_enter_mode: user=%s params=%s", user_id, params)


def handle_view_progress(user_id: UUID, params: dict) -> None:
    logger.info("Stub handle_view_progress: user=%s params=%s", user_id, params)


def handle_start_practice(user_id: UUID, params: dict) -> None:
    logger.info("Stub handle_start_practice: user=%s params=%s", user_id, params)


def handle_enter_wrong_mode(user_id: UUID, params: dict) -> None:
    logger.info("Stub handle_enter_wrong_mode: user=%s params=%s", user_id, params)


def handle_reset_unit(user_id: UUID, params: dict) -> None:
    logger.info("Stub handle_reset_unit: user=%s params=%s", user_id, params)


def handle_back(user_id: UUID, params: dict) -> None:
    logger.info("Stub handle_back: user=%s params=%s", user_id, params)


def handle_ai_tutor_prompt(user_id: UUID, params: dict) -> None:
    logger.info("Stub handle_ai_tutor_prompt: user=%s params=%s", user_id, params)


def handle_review_wrong(user_id: UUID, params: dict) -> None:
    logger.info("Stub handle_review_wrong: user=%s params=%s", user_id, params)


ACTION_HANDLERS = {
    "enter_mode": handle_enter_mode,
    "view_progress": handle_view_progress,
    "start_practice": handle_start_practice,
    "enter_wrong_mode": handle_enter_wrong_mode,
    "reset_unit": handle_reset_unit,
    "back": handle_back,
    "ai_tutor_prompt": handle_ai_tutor_prompt,
    "review_wrong": handle_review_wrong,
}


def dispatch(action: Optional[str], params: dict, user_id: UUID) -> None:
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        logger.warning("No handler registered for action=%s params=%s", action, params)
        return
    handler(user_id, params)
