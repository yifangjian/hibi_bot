import io
import random
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.db.client import supabase

BUCKET = "completion-cards"

WIDTH, HEIGHT = 1000, 1000
BACKGROUND = (250, 243, 227)  # #FAF3E3
NAVY = (28, 43, 68)  # #1C2B44
CORAL = (178, 58, 58)  # #B23A3A
MUTED = (138, 133, 120)  # #8A8578
GOLD = (200, 160, 90)

FONT_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts" / "NotoSansTC-Bold.otf"


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), size)


def _draw_confetti(draw: ImageDraw.ImageDraw) -> None:
    colors = [NAVY, CORAL, GOLD]
    for _ in range(70):
        x = random.randint(0, WIDTH)
        y = random.randint(0, 160)
        color = random.choice(colors)
        size = random.randint(6, 16)
        if random.random() < 0.5:
            draw.ellipse([x, y, x + size, y + size], fill=color)
        else:
            draw.rectangle([x, y, x + size, y + size // 2], fill=color)


def generate_completion_image(display_name: str, accuracy_pct: int, date_str: str) -> str:
    """產生每日挑戰完成圖卡，上傳到 Supabase Storage public bucket，回傳公開 URL。"""
    img = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(img)

    _draw_confetti(draw)

    title_font = _font(64)
    name_font = _font(44)
    stat_font = _font(96)
    label_font = _font(32)

    draw.text((WIDTH // 2, 230), "每日挑戰完成！", font=title_font, fill=NAVY, anchor="mm")
    draw.text((WIDTH // 2, 330), display_name, font=name_font, fill=NAVY, anchor="mm")

    draw.rounded_rectangle([150, 430, 850, 720], radius=30, outline=NAVY, width=4)
    draw.text((WIDTH // 2, 540), f"{accuracy_pct}%", font=stat_font, fill=CORAL, anchor="mm")
    draw.text((WIDTH // 2, 650), "答對率", font=label_font, fill=MUTED, anchor="mm")

    draw.text((WIDTH // 2, 800), date_str, font=label_font, fill=MUTED, anchor="mm")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    filename = f"{uuid.uuid4()}.png"
    supabase.storage.from_(BUCKET).upload(filename, buffer.read(), file_options={"content-type": "image/png"})

    return supabase.storage.from_(BUCKET).get_public_url(filename)
