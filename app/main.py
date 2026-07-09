import logging

from fastapi import FastAPI

from app.routers import internal, webhook

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="hibi_bot")

app.include_router(webhook.router)
app.include_router(internal.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
