from openai import OpenAI

from app.config import settings


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def chat_completion(messages: list[dict]) -> str:
    response = _client().chat.completions.create(model=settings.openai_model, messages=messages)
    return response.choices[0].message.content
