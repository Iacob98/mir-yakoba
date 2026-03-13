"""Animated achievement GIF generation using Pillow."""

import logging
import math
import random
import textwrap
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.config import settings

logger = logging.getLogger(__name__)

WIDTH = 600
HEIGHT = 400
TOTAL_FRAMES = 40
FRAME_DURATION = 50  # ms per frame

# Soft light color schemes per milestone
SCHEMES = {
    1: {
        "bg": (245, 247, 250),
        "bar_from": (167, 199, 231),
        "bar_to": (108, 160, 220),
        "glow": (108, 160, 220),
        "accent": (70, 130, 200),
        "text": (50, 55, 65),
        "sub": (120, 130, 145),
        "badge_bg": (108, 160, 220),
        "badge_text": (255, 255, 255),
        "star": (255, 210, 80),
    },
    5: {
        "bg": (250, 247, 240),
        "bar_from": (240, 190, 100),
        "bar_to": (230, 160, 50),
        "glow": (240, 180, 60),
        "accent": (200, 140, 30),
        "text": (55, 50, 40),
        "sub": (140, 130, 110),
        "badge_bg": (230, 160, 50),
        "badge_text": (255, 255, 255),
        "star": (255, 220, 100),
    },
    10: {
        "bg": (248, 243, 250),
        "bar_from": (190, 140, 210),
        "bar_to": (160, 90, 200),
        "glow": (170, 100, 210),
        "accent": (140, 70, 180),
        "text": (55, 40, 65),
        "sub": (130, 115, 140),
        "badge_bg": (160, 90, 200),
        "badge_text": (255, 255, 255),
        "star": (255, 210, 120),
    },
}

# Pre-generate sparkle positions
random.seed(42)
SPARKLES = [(random.randint(40, WIDTH - 40), random.randint(20, HEIGHT - 20)) for _ in range(18)]


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    font_paths = [
        "/usr/share/fonts/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    ]
    for path in font_paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _get_font_regular(size: int) -> ImageFont.FreeTypeFont:
    font_paths = [
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    ]
    for path in font_paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    """Linear interpolation between two colors."""
    t = max(0.0, min(1.0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _ease_out_back(t: float) -> float:
    """Ease-out-back for bouncy pop-in."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


def _ease_out_cubic(t: float) -> float:
    return 1 - pow(1 - t, 3)


def _draw_star(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: float, color: tuple, alpha_img: Image.Image = None):
    """Draw a 4-point star/sparkle."""
    if r < 1:
        return
    ri = r * 0.35
    points = []
    for i in range(8):
        angle = math.pi / 4 * i - math.pi / 2
        rad = r if i % 2 == 0 else ri
        points.append((cx + rad * math.cos(angle), cy + rad * math.sin(angle)))
    draw.polygon(points, fill=color)


def _draw_rounded_rect(draw: ImageDraw.ImageDraw, xy: tuple, radius: int, fill: tuple):
    """Draw a rounded rectangle."""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _render_frame(
    frame_idx: int,
    user_name: str,
    level: int,
    title: str,
    description: str,
    scheme: dict,
) -> Image.Image:
    """Render a single animation frame."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), scheme["bg"] + (255,))
    draw = ImageDraw.Draw(img)

    t = frame_idx / (TOTAL_FRAMES - 1)  # 0..1 overall progress

    # === Phase timing ===
    # 0.0-0.4: bar fills up
    # 0.3-0.6: bar overflows + flash
    # 0.4-1.0: badge + text appear, sparkles

    # --- XP bar ---
    bar_x = 80
    bar_y = 175
    bar_w = WIDTH - 160
    bar_h = 28
    bar_r = 14

    # Bar background (soft gray)
    _draw_rounded_rect(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), bar_r, (220, 225, 230))

    # Bar fill progress
    bar_progress = min(1.0, _ease_out_cubic(t / 0.4)) if t < 0.4 else 1.0

    # Overflow glow (bar goes beyond 100%)
    overflow = 0.0
    if t > 0.3:
        overflow_t = min(1.0, (t - 0.3) / 0.2)
        overflow = 0.15 * math.sin(overflow_t * math.pi)

    fill_w = int(bar_w * min(1.0, bar_progress + overflow))
    if fill_w > 2:
        bar_color = _lerp_color(scheme["bar_from"], scheme["bar_to"], bar_progress)
        _draw_rounded_rect(
            draw,
            (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h),
            bar_r,
            bar_color,
        )

    # Glow pulse on overflow
    if t > 0.3 and t < 0.65:
        glow_t = (t - 0.3) / 0.35
        glow_alpha = int(60 * math.sin(glow_t * math.pi))
        if glow_alpha > 0:
            glow_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_layer)
            glow_color = scheme["glow"] + (glow_alpha,)
            _draw_rounded_rect(
                glow_draw,
                (bar_x - 4, bar_y - 4, bar_x + bar_w + 4, bar_y + bar_h + 4),
                bar_r + 4,
                glow_color,
            )
            img = Image.alpha_composite(img, glow_layer)
            draw = ImageDraw.Draw(img)

    # Bar label text
    bar_font = _get_font_regular(13)
    if t < 0.5:
        pct = int(bar_progress * 100)
        bar_label = f"XP {pct}%"
    else:
        bar_label = "MAX!"
    bbox = draw.textbbox((0, 0), bar_label, font=bar_font)
    tw = bbox[2] - bbox[0]
    bar_label_color = scheme["sub"] if t < 0.5 else scheme["accent"]
    draw.text(
        ((WIDTH - tw) // 2, bar_y + bar_h + 6),
        bar_label,
        fill=bar_label_color,
        font=bar_font,
    )

    # "Lv. X-1 → Lv. X" text above bar
    if t < 0.55:
        level_label_font = _get_font_regular(14)
        prev_level = f"Lv.{level - 1}" if level > 1 else "Lv.0"
        level_label = f"{prev_level}  →  Lv.{level}"
        bbox = draw.textbbox((0, 0), level_label, font=level_label_font)
        tw = bbox[2] - bbox[0]
        draw.text(
            ((WIDTH - tw) // 2, bar_y - 24),
            level_label,
            fill=scheme["sub"],
            font=level_label_font,
        )

    # === LEVEL UP badge (appears after bar fills) ===
    badge_appear_t = max(0.0, min(1.0, (t - 0.42) / 0.18))
    if badge_appear_t > 0:
        scale = _ease_out_back(badge_appear_t)
        badge_r = int(36 * scale)
        badge_cx = WIDTH // 2
        badge_cy = 75

        if badge_r > 2:
            # Badge shadow
            shadow_color = scheme["badge_bg"][:3] + (40,)
            shadow_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_layer)
            shadow_draw.ellipse(
                [badge_cx - badge_r - 2, badge_cy - badge_r + 3,
                 badge_cx + badge_r + 2, badge_cy + badge_r + 7],
                fill=shadow_color,
            )
            img = Image.alpha_composite(img, shadow_layer)
            draw = ImageDraw.Draw(img)

            # Badge circle
            draw.ellipse(
                [badge_cx - badge_r, badge_cy - badge_r,
                 badge_cx + badge_r, badge_cy + badge_r],
                fill=scheme["badge_bg"],
            )

            # Level number
            level_font_size = max(8, int(28 * scale))
            level_font = _get_font(level_font_size)
            level_text = str(level)
            bbox = draw.textbbox((0, 0), level_text, font=level_font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(
                (badge_cx - tw // 2, badge_cy - th // 2 - 1),
                level_text,
                fill=scheme["badge_text"],
                font=level_font,
            )

    # === Title (LEVEL UP!) ===
    title_appear_t = max(0.0, min(1.0, (t - 0.5) / 0.15))
    if title_appear_t > 0:
        title_font = _get_font(26)
        # Slide up + fade
        offset_y = int(15 * (1 - _ease_out_cubic(title_appear_t)))
        title_text = f"LEVEL UP!"
        bbox = draw.textbbox((0, 0), title_text, font=title_font)
        tw = bbox[2] - bbox[0]

        title_alpha = int(255 * min(1.0, title_appear_t * 2))
        title_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        title_draw = ImageDraw.Draw(title_layer)
        title_draw.text(
            ((WIDTH - tw) // 2, 125 + offset_y),
            title_text,
            fill=scheme["accent"] + (title_alpha,),
            font=title_font,
        )
        img = Image.alpha_composite(img, title_layer)
        draw = ImageDraw.Draw(img)

    # === Achievement title + name + description ===
    info_appear_t = max(0.0, min(1.0, (t - 0.6) / 0.2))
    if info_appear_t > 0:
        alpha = int(255 * _ease_out_cubic(info_appear_t))
        offset_y = int(10 * (1 - _ease_out_cubic(info_appear_t)))

        info_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        info_draw = ImageDraw.Draw(info_layer)

        # Achievement title
        ach_font = _get_font(20)
        bbox = info_draw.textbbox((0, 0), title, font=ach_font)
        tw = bbox[2] - bbox[0]
        info_draw.text(
            ((WIDTH - tw) // 2, 230 + offset_y),
            title,
            fill=scheme["text"] + (alpha,),
            font=ach_font,
        )

        # User name
        name_font = _get_font_regular(15)
        name_text = user_name
        bbox = info_draw.textbbox((0, 0), name_text, font=name_font)
        tw = bbox[2] - bbox[0]
        info_draw.text(
            ((WIDTH - tw) // 2, 258 + offset_y),
            name_text,
            fill=scheme["sub"] + (alpha,),
            font=name_font,
        )

        # Description
        desc_font = _get_font_regular(13)
        wrapped = textwrap.wrap(description, width=55)
        y = 290 + offset_y
        for line in wrapped[:3]:
            bbox = info_draw.textbbox((0, 0), line, font=desc_font)
            tw = bbox[2] - bbox[0]
            info_draw.text(
                ((WIDTH - tw) // 2, y),
                line,
                fill=scheme["sub"] + (alpha,),
                font=desc_font,
            )
            y += 20

        img = Image.alpha_composite(img, info_layer)
        draw = ImageDraw.Draw(img)

    # === Sparkles ===
    if t > 0.45:
        sparkle_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        sparkle_draw = ImageDraw.Draw(sparkle_layer)

        for i, (sx, sy) in enumerate(SPARKLES):
            # Each sparkle has its own timing offset
            delay = 0.45 + (i * 0.02)
            sparkle_t = max(0.0, min(1.0, (t - delay) / 0.3))
            if sparkle_t <= 0:
                continue

            # Pop in then fade
            if sparkle_t < 0.5:
                s = _ease_out_back(sparkle_t * 2)
                a = 1.0
            else:
                s = 1.0 - (sparkle_t - 0.5) * 2
                a = 1.0 - (sparkle_t - 0.5) * 2

            star_r = max(0, int(8 * s + 3 * math.sin(i)))
            star_alpha = int(200 * max(0, a))
            star_color = scheme["star"] + (star_alpha,)
            _draw_star(sparkle_draw, sx, sy, star_r, star_color)

        img = Image.alpha_composite(img, sparkle_layer)

    return img.convert("RGB")


def generate_achievement_image(
    user_name: str,
    level: int,
    title: str,
    description: str,
) -> str:
    """
    Generate animated achievement GIF. Returns relative file path (for /uploads/).
    """
    scheme = SCHEMES.get(level, SCHEMES[1])

    frames = []
    for i in range(TOTAL_FRAMES):
        frame = _render_frame(i, user_name, level, title, description, scheme)
        frames.append(frame)

    # Hold last frame longer
    for _ in range(20):
        frames.append(frames[-1])

    filename = f"achievement_{uuid.uuid4().hex[:12]}.gif"
    save_dir = settings.upload_dir / "images"
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / filename

    frames[0].save(
        save_path,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION,
        loop=0,
        optimize=True,
    )

    rel_path = f"images/{filename}"
    logger.info(f"Generated achievement GIF: {rel_path}")
    return rel_path
