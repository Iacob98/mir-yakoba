# Webseit

Personal blog with Telegram integration.

## Features

- 4 access levels (public, registered, premium_1, premium_2)
- Posts with markdown, full-text search
- Media hosting (photos, audio, video)
- Comments
- Telegram bot authentication
- Admin panel

## Quick Start

```bash
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN

docker compose up -d
docker compose exec app alembic upgrade head
```

## Tech Stack

- FastAPI + SQLAlchemy 2.0
- PostgreSQL + Redis
- htmx + Tailwind CSS
- aiogram (Telegram bot)
- Docker Compose
